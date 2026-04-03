from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

from dotenv import load_dotenv

from crypto_alpha_arena.agents.base import PricePredictorAgent
from crypto_alpha_arena.market_feed import Candle
from crypto_alpha_arena.models import (
    LeaderboardRow,
    PredictionLogRow,
    PricePrediction,
    SessionResult,
    TickObservation,
)
from crypto_alpha_arena.prediction_sim import SimConfig, settle_one


class Feed(Protocol):
    symbols: list[str]

    def step(self, t: int) -> dict[str, Candle]: ...

    def closes(self, symbol: str, lookback: int) -> list[float]: ...


load_dotenv()


def _returns(closes: list[float]) -> tuple[float, float, float]:
    if len(closes) < 2:
        return 0.0, 0.0, 0.0
    c = closes[-1]
    r1 = (c / closes[-2] - 1.0) if len(closes) >= 2 else 0.0
    r5 = (c / closes[-6] - 1.0) if len(closes) >= 6 else r1
    r20 = (c / closes[-21] - 1.0) if len(closes) >= 21 else r5
    return r1, r5, r20


@dataclass
class ArenaConfig:
    initial_cash_usd: float = 10_000.0
    steps: int = 200
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
    seed: int = 7
    sim: SimConfig = SimConfig()


def run_arena(
    agents: Sequence[PricePredictorAgent],
    feed: Feed,
    config: Optional[ArenaConfig] = None,
) -> SessionResult:
    """
    Each step: (if t>=1) settle last predictions vs realized one-step return,
    then each agent issues a new **next-step return** forecast; simulated long/short PnL only.
    """
    cfg = config or ArenaConfig()
    sim_cfg = cfg.sim
    equity: dict[str, float] = {a.agent_id: float(cfg.initial_cash_usd) for a in agents}
    names = {a.agent_id: a.name for a in agents}

    equity_curves: dict[str, list[tuple[int, float]]] = {a.agent_id: [] for a in agents}
    pending: dict[tuple[str, str], PricePrediction] = {}
    prediction_logs: list[PredictionLogRow] = []

    stats: dict[str, dict[str, float]] = {
        aid: {"dir_hit": 0.0, "dir_tot": 0.0, "mae_sum": 0.0, "mae_n": 0.0}
        for aid in equity
    }

    prev_close: dict[str, Optional[float]] = {s: None for s in feed.symbols}

    for t in range(cfg.steps):
        candles = feed.step(t)
        prices = {s: candles[s].close for s in feed.symbols}

        if t > 0:
            for key, pred in list(pending.items()):
                aid, sym = key
                pc = prev_close.get(sym)
                if pc is None or pc <= 0:
                    continue
                actual_r = prices[sym] / pc - 1.0
                eq = max(equity[aid], 1.0)
                pnl, row = settle_one(
                    step=t,
                    agent_id=aid,
                    pred=pred,
                    actual_return=actual_r,
                    equity=eq,
                    cfg=sim_cfg,
                )
                prediction_logs.append(row)
                equity[aid] = max(0.0, equity[aid] + pnl)

                st = stats[aid]
                st["mae_sum"] += abs(pred.pred_return_next - actual_r)
                st["mae_n"] += 1.0
                if row.direction_hit is True:
                    st["dir_hit"] += 1.0
                    st["dir_tot"] += 1.0
                elif row.direction_hit is False:
                    st["dir_tot"] += 1.0

        pending.clear()

        for agent in agents:
            aid = agent.agent_id
            for sym in feed.symbols:
                closes = feed.closes(sym, 40)
                c = candles[sym].close
                r1, r5, r20 = _returns(closes if closes else [c, c])
                obs = TickObservation(
                    step=t,
                    symbol=sym,
                    mid=c,
                    ret_1=r1,
                    ret_5=r5,
                    ret_20=r20,
                    equity_usd=equity[aid],
                    cash_usd=equity[aid],
                    position_qty=0.0,
                    unrealized_pnl_usd=0.0,
                )
                pr = agent.predict(obs)
                if pr is not None and pr.symbol == sym:
                    pending[(aid, sym)] = pr

        for s in feed.symbols:
            prev_close[s] = prices[s]

        for aid in equity_curves:
            equity_curves[aid].append((t, equity[aid]))

    initial = float(cfg.initial_cash_usd)

    def max_dd(series: list[tuple[int, float]]) -> float:
        peak = series[0][1]
        mdd = 0.0
        for _, v in series:
            peak = max(peak, v)
            dd = (peak - v) / peak if peak > 0 else 0.0
            mdd = max(mdd, dd)
        return mdd * 100.0

    last_eq = {aid: equity_curves[aid][-1][1] for aid in equity_curves}
    ranked_ids = sorted(last_eq.keys(), key=lambda i: last_eq[i], reverse=True)

    rows: list[LeaderboardRow] = []
    for rank, aid in enumerate(ranked_ids, start=1):
        st = stats[aid]
        dir_acc = (st["dir_hit"] / st["dir_tot"] * 100.0) if st["dir_tot"] > 0 else 0.0
        mae = (st["mae_sum"] / st["mae_n"]) if st["mae_n"] > 0 else 0.0
        eq = last_eq[aid]
        rows.append(
            LeaderboardRow(
                rank=rank,
                agent_id=aid,
                name=names[aid],
                equity_usd=eq,
                return_pct=(eq / initial - 1.0) * 100.0,
                max_drawdown_pct=max_dd(equity_curves[aid]),
                direction_accuracy_pct=dir_acc,
                mae_return=mae,
            )
        )

    meta: dict[str, Any] = {
        "initial_cash_usd": initial,
        "steps": cfg.steps,
        "symbols": list(cfg.symbols),
        "mode": "prediction_sim",
    }
    return SessionResult(
        meta=meta,
        equity_curves=equity_curves,
        fills=[],
        leaderboard=rows,
        prediction_logs=prediction_logs,
    )


def default_agents(seed: int = 0) -> list[PricePredictorAgent]:
    from crypto_alpha_arena.agents.llm_agent import LLMPredictorAgent
    from crypto_alpha_arena.agents.rule_agents import (
        MeanReversionPredictor,
        MomentumPredictor,
        RandomPredictor,
        TrendPredictor,
    )

    agents: list[PricePredictorAgent] = [
        MomentumPredictor("m_btc", "BTCUSDT"),
        MomentumPredictor("m_eth", "ETHUSDT"),
        MeanReversionPredictor("mr_btc", "BTCUSDT"),
        TrendPredictor("tr_eth", "ETHUSDT"),
        RandomPredictor("noise_eth", "ETHUSDT", seed=seed + 3),
    ]
    if os.getenv("OPENAI_API_KEY"):
        agents.insert(
            0,
            LLMPredictorAgent("llm_btc", "LLM predictor (BTC)", default_symbol="BTCUSDT"),
        )
    return agents
