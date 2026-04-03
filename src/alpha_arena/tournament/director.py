from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from alpha_arena.agents.base import BaseAgent
from alpha_arena.config import settings
from alpha_arena.data.live_context import fetch_macro_and_coinglass
from alpha_arena.data.market_state import build_market_state
from alpha_arena.engine.execution import check_tp_sl, execute_action, mark_portfolio_to_market
from alpha_arena.models import (
    AgentInfo,
    AgentMetrics,
    CoinGlassSnapshot,
    LeaderboardEntry,
    MacroRegimeSignal,
    OHLCVBar,
    PortfolioState,
    TradeAction,
)
from alpha_arena.tournament.scoring import (
    composite_score,
    diversity_factors,
    max_drawdown_pct,
    sharpe_ratio,
    sortino_ratio,
)


@dataclass
class TournamentDirector:
    agents: Sequence[BaseAgent]
    initial_equity: float = 100_000.0
    enable_live: bool = False
    live_symbol: str = "BTC"
    metrics: dict[str, AgentMetrics] = field(default_factory=dict)
    portfolios: dict[str, PortfolioState] = field(default_factory=dict)
    equity_curves: dict[str, list[float]] = field(default_factory=dict)
    last_leaderboard: list[LeaderboardEntry] = field(default_factory=list)
    last_macro: MacroRegimeSignal = field(default_factory=MacroRegimeSignal)
    last_coinglass: CoinGlassSnapshot = field(default_factory=CoinGlassSnapshot)

    def __post_init__(self) -> None:
        for a in self.agents:
            self.metrics[a.agent_id] = AgentMetrics(
                agent_id=a.agent_id,
                name=a.name,
                equity_usd=self.initial_equity,
                peak_equity_usd=self.initial_equity,
                returns=[],
                liquidated=False,
            )
            self.portfolios[a.agent_id] = PortfolioState(
                cash_usd=self.initial_equity,
                equity_usd=self.initial_equity,
                open_positions=[],
            )
            self.equity_curves[a.agent_id] = [self.initial_equity]

    def _agent_registry(self) -> list[AgentInfo]:
        reg = [AgentInfo(agent_id=a.agent_id, name=a.name, role="trading") for a in self.agents]
        reg.append(AgentInfo(agent_id="macro_news", name="Macro/News Agent", role="macro"))
        return reg

    async def run_step(
        self,
        *,
        step_index: int,
        ts: datetime,
        bars_1m: list[OHLCVBar],
        bars_5m: list[OHLCVBar],
        primary_ticker: str,
        mark_price: float,
        bar_volume: float,
    ) -> None:
        for aid in self.portfolios:
            self.portfolios[aid] = mark_portfolio_to_market(self.portfolios[aid], mark_price)

        if self.enable_live:
            macro, cg = await fetch_macro_and_coinglass(self.live_symbol)
        else:
            macro = MacroRegimeSignal(
                regime="neutral",
                confidence=0.35,
                reasoning="Live macro/CoinGlass disabled (set ALPHA_ARENA_LIVE=1 for real fetch).",
            )
            cg = CoinGlassSnapshot(ok=False, error="live_fetch_disabled")
        self.last_macro = macro
        self.last_coinglass = cg
        registry = self._agent_registry()

        async def gen(agent: BaseAgent) -> tuple[str, TradeAction]:
            state = build_market_state(
                step_index=step_index,
                ts=ts,
                primary_ticker=primary_ticker,
                bars_1m=bars_1m,
                bars_5m=bars_5m,
                portfolio=self.portfolios[agent.agent_id],
                macro=macro,
                coinglass=cg,
                agent_registry=registry,
            )
            action = await agent.generate_action(state)
            return agent.agent_id, action

        results = await asyncio.gather(*[gen(a) for a in self.agents])
        actions = {aid: act for aid, act in results}
        tickers = [actions[a.agent_id].ticker for a in self.agents]
        div = diversity_factors(tickers, [a.agent_id for a in self.agents])

        for agent in self.agents:
            m = self.metrics[agent.agent_id]
            if m.liquidated:
                continue
            port = self.portfolios[agent.agent_id]
            prev_eq = port.equity_usd
            act = actions[agent.agent_id]
            # Avoid churn: same ticker + same direction as open position → hold (no new fees)
            if port.open_positions and act.signal != "NEUTRAL":
                p0 = port.open_positions[0]
                if (
                    len(port.open_positions) == 1
                    and p0.ticker == act.ticker
                    and (
                        (act.signal == "LONG" and p0.side == "LONG")
                        or (act.signal == "SHORT" and p0.side == "SHORT")
                    )
                ):
                    port = mark_portfolio_to_market(port, mark_price)
                    self.portfolios[agent.agent_id] = port
                    eq = port.equity_usd
                    ret = (eq / prev_eq - 1.0) if prev_eq > 0 else 0.0
                    m.returns.append(ret)
                    m.equity_usd = eq
                    m.peak_equity_usd = max(m.peak_equity_usd, eq)
                    self.equity_curves[agent.agent_id].append(m.equity_usd)
                    continue

            ms = build_market_state(
                step_index=step_index,
                ts=ts,
                primary_ticker=primary_ticker,
                bars_1m=bars_1m,
                bars_5m=bars_5m,
                portfolio=port,
                macro=macro,
                coinglass=cg,
                agent_registry=registry,
            )
            port2, _ = execute_action(
                agent_id=agent.agent_id,
                action=act,
                state=ms,
                portfolio=port,
                mark_price=mark_price,
                bar_volume=bar_volume,
            )
            port2 = check_tp_sl(port2, mark_price)
            port2 = mark_portfolio_to_market(port2, mark_price)
            self.portfolios[agent.agent_id] = port2

            eq = port2.equity_usd
            ret = (eq / prev_eq - 1.0) if prev_eq > 0 else 0.0
            m.returns.append(ret)
            m.equity_usd = eq
            m.peak_equity_usd = max(m.peak_equity_usd, eq)
            dd = (m.peak_equity_usd - eq) / m.peak_equity_usd if m.peak_equity_usd > 0 else 0.0
            if dd >= settings.max_drawdown_liquidation_pct:
                m.liquidated = True
                m.equity_usd = max(0.0, eq * 0.5)
                self.portfolios[agent.agent_id] = PortfolioState(
                    cash_usd=m.equity_usd,
                    equity_usd=m.equity_usd,
                    open_positions=[],
                )
            self.equity_curves[agent.agent_id].append(m.equity_usd)

        self._rebuild_leaderboard(div)

    def _rebuild_leaderboard(self, diversity: dict[str, float]) -> None:
        entries: list[LeaderboardEntry] = []
        for agent in self.agents:
            m = self.metrics[agent.agent_id]
            curve = self.equity_curves[agent.agent_id]
            rets = m.returns
            sh = sharpe_ratio(rets, settings.bars_per_year)
            so = sortino_ratio(rets, settings.bars_per_year)
            mdd = max_drawdown_pct(curve)
            tr = (m.equity_usd / self.initial_equity - 1.0) * 100.0
            div_f = diversity.get(agent.agent_id, 1.0)
            sc = composite_score(
                total_return=tr,
                sharpe=sh,
                sortino=so,
                max_dd_pct=mdd,
                diversity_factor=div_f,
            )
            entries.append(
                LeaderboardEntry(
                    agent_id=agent.agent_id,
                    name=m.name,
                    equity_usd=m.equity_usd,
                    total_return=tr,
                    sharpe_ratio=sh,
                    sortino_ratio=so,
                    max_drawdown_pct=mdd,
                    diversity_factor=div_f,
                    score=sc,
                )
            )
        entries.sort(key=lambda e: e.score, reverse=True)
        self.last_leaderboard = entries
