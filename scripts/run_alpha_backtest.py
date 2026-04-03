#!/usr/bin/env python3
"""Run backtest on sample CSV and register state for FastAPI dashboard."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from alpha_arena.agents.heuristic_agent import HeuristicAgent
from alpha_arena.backtest.engine import BacktestEngine
from alpha_arena.data.live_context import fetch_macro_and_coinglass
from alpha_arena.models import CoinGlassSnapshot, MacroRegimeSignal
from alpha_arena.persistence import save_leaderboard_snapshot, save_live_context_snapshot
from alpha_arena.state import set_tournament_director


async def main() -> None:
    csv_path = ROOT / "data" / "btc_sample.csv"
    agents = [
        HeuristicAgent("h1", "Momentum-A", bias_long=True),
        HeuristicAgent("h2", "Momentum-B", bias_long=False),
        HeuristicAgent("h3", "Momentum-C", bias_long=True),
    ]
    eng = BacktestEngine(agents, initial_equity=100_000.0)

    def on_day(day: str, lb: list) -> None:
        print(f"--- Day {day} leaderboard (top): {lb[0].name if lb else 'n/a'} score={lb[0].score if lb else 0:.4f}")

    d = await eng.run_csv(csv_path, primary_ticker="BTC/USDT", on_day_end=on_day)
    set_tournament_director(d)

    trading_meta = [{"agent_id": a.agent_id, "name": a.name, "role": "trading"} for a in agents]
    try:
        macro, cg = await fetch_macro_and_coinglass("BTC")
    except Exception as e:
        macro = MacroRegimeSignal(regime="neutral", reasoning=f"live_fetch_error:{e!s}")
        cg = CoinGlassSnapshot(ok=False, error=str(e))

    ctx_path = save_live_context_snapshot(macro, cg, trading_agents=trading_meta)
    out_path = save_leaderboard_snapshot(
        d.last_leaderboard,
        meta={
            "source": str(csv_path),
            "script": "run_alpha_backtest.py",
            "macro": macro.model_dump(mode="json"),
            "coinglass": cg.model_dump(mode="json"),
            "agents": trading_meta
            + [{"agent_id": "macro_news", "name": "Macro/News Agent", "role": "macro"}],
        },
    )

    print("\nFinal leaderboard (by composite score):")
    for e in d.last_leaderboard:
        print(
            f"  {e.name}: equity={e.equity_usd:,.2f} ret%={e.total_return:.2f} "
            f"sharpe={e.sharpe_ratio:.3f} sortino={e.sortino_ratio:.3f} "
            f"mdd%={e.max_drawdown_pct:.2f} score={e.score:.4f}"
        )
    print(f"\nLeaderboard: {out_path}")
    print(f"Live macro + CoinGlass snapshot: {ctx_path}")
    print("API: PYTHONPATH=src python -m uvicorn alpha_arena.api.main:app --host 127.0.0.1 --port 8765")


if __name__ == "__main__":
    asyncio.run(main())
