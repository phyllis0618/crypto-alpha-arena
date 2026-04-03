#!/usr/bin/env python3
"""Run global expansion simulation → dashboard PNG + Executive_Summary.md."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yanfu_global_expansion.backtester import DEFAULT_SIMULATION_TRADING_DAYS, CrossMarketBacktester
from yanfu_global_expansion.pitch_dashboard import render_expansion_dashboard
from yanfu_global_expansion.roadmap_report import build_executive_summary, write_executive_summary
from yanfu_global_expansion.universe_defaults import build_default_universe


DISPLAY_NAMES = {
    "CN_CSI1000": "CN CSI1000",
    "CN_CSI500": "CN CSI500",
    "HK_HSTECH": "HK HSTECH",
    "US_SP500": "US S&P500",
    "US_RUT2000": "US RUT2000",
    "IN_NIFTY50": "IN Nifty50",
    "VN_VNI": "VN VNI",
    "CRYPTO_ETF_IBIT": "Crypto ETF (IBIT)",
    "CRYPTO_ETF_ETHW": "Crypto ETF (ETHW)",
}


async def _async_main(args: argparse.Namespace) -> None:
    universe = build_default_universe()
    bt = CrossMarketBacktester(
        universe,
        n_trading_days=args.days,
        seed=args.seed,
    )
    await bt.ingest_synthetic_universe()
    result = bt.run_sync()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    png = out_dir / "yanfu_global_expansion_dashboard.png"
    render_expansion_dashboard(result, DISPLAY_NAMES, png)

    summary = build_executive_summary(result, target_aum_usd_bn=args.target_aum_bn)
    md_path = out_dir / "Executive_Summary.md"
    write_executive_summary(md_path, summary)

    metrics = {
        "sharpes_by_sleeve": result.sharpes_by_sleeve,
        "sortino_core_global_blend": result.sortino_core,
        "sortino_with_crypto_booster": result.sortino_with_crypto,
        "beta_neutral_meta_sample": result.beta_neutral_meta,
    }
    (out_dir / "expansion_sim_metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print(png)
    print(md_path)


def main() -> None:
    p = argparse.ArgumentParser(description="Global expansion roadmap simulation (synthetic).")
    p.add_argument("--out-dir", type=Path, default=ROOT / "outputs")
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_SIMULATION_TRADING_DAYS,
        help=f"Simulation horizon in sessions (default {DEFAULT_SIMULATION_TRADING_DAYS} ≈ 18 months).",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--target-aum-bn", type=float, default=5.0)
    args = p.parse_args()
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
