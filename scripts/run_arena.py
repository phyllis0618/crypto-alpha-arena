#!/usr/bin/env python3
"""Run one prediction + simulated-trading competition session (CLI)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crypto_alpha_arena.arena import ArenaConfig, default_agents, run_arena
from crypto_alpha_arena.market_feed import build_feed_from_env


def main() -> None:
    p = argparse.ArgumentParser(
        description="Crypto Alpha Arena — predict returns, simulate long/short PnL (no live trading)"
    )
    p.add_argument("--steps", type=int, default=250)
    p.add_argument("--cash", type=float, default=10_000.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=ROOT / "outputs" / "last_session.json")
    args = p.parse_args()

    feed, mode = build_feed_from_env(["BTCUSDT", "ETHUSDT"], seed=args.seed)
    agents = default_agents(seed=args.seed)
    cfg = ArenaConfig(
        initial_cash_usd=args.cash,
        steps=args.steps,
        symbols=("BTCUSDT", "ETHUSDT"),
        seed=args.seed,
    )
    result = run_arena(agents, feed, cfg)
    result.meta["feed_mode"] = mode

    args.out.parent.mkdir(parents=True, exist_ok=True)
    logs_sample = [r.model_dump() for r in result.prediction_logs[:200]]
    payload = {
        "meta": result.meta,
        "leaderboard": [r.model_dump() for r in result.leaderboard],
        "equity_curves": {
            k: [[a, b] for a, b in v] for k, v in result.equity_curves.items()
        },
        "prediction_logs_sample": logs_sample,
        "prediction_logs_total": len(result.prediction_logs),
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Feed: {mode} | agents: {len(agents)} | steps: {args.steps} | mode: prediction_sim")
    for row in result.leaderboard:
        print(
            f"  {row.rank}. {row.name}  equity=${row.equity_usd:,.2f}  "
            f"return={row.return_pct:+.2f}%  mdd={row.max_drawdown_pct:.2f}%  "
            f"dir_acc={row.direction_accuracy_pct:.1f}%  mae={row.mae_return:.6f}"
        )
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
