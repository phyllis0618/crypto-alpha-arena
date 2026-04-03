#!/usr/bin/env python3
"""Generate outputs/yanfu_v2_roadmap_analysis.png — SEA mirror + US Special Ops validation dashboard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yanfu_v2_roadmap import (
    MarketMirror,
    build_pivot_timeline,
    render_v2_roadmap_dashboard,
    strategic_sharpness_demo,
)


def main() -> None:
    p = argparse.ArgumentParser(description="V2 global roadmap validation figure (synthetic).")
    p.add_argument("--out", type=Path, default=ROOT / "outputs" / "yanfu_v2_roadmap_analysis.png")
    p.add_argument("--json", type=Path, default=None, help="Optional mirror metrics JSON path")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--days", type=int, default=378, help="Trading days (~18m default ≈ 252×1.5)")
    args = p.parse_args()

    mm = MarketMirror(seed=args.seed)
    mirror_result = mm.run(n_days=args.days)
    pivot = build_pivot_timeline(n_trading_days=args.days, seed=args.seed + 1)
    sharp = strategic_sharpness_demo(seed=args.seed + 2)

    render_v2_roadmap_dashboard(mirror_result, pivot, args.out, sharpness=sharp)

    if args.json:
        payload = {
            "ic_mean_by_market": mirror_result.ic_mean_by_market,
            "ir_by_market": mirror_result.ir_by_market,
            "decay_ratio_sea_vs_us": float(mirror_result.decay_ratio_sea_vs_us),
            "turnover_efficiency": mirror_result.turnover_efficiency,
            "settlement_friction_bps": mirror_result.settlement_friction_bps,
            "strategic_sharpe_priors": sharp,
            "pivot_end_equity_index": float(pivot.equity_curve[-1] / pivot.equity_curve[0]),
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(args.json)

    print(args.out)


if __name__ == "__main__":
    main()
