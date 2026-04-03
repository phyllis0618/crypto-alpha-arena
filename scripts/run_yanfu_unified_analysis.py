#!/usr/bin/env python3
"""
一次性跑完：真实数据 Harvest → Research（DNA/Gap/对比图）→ Global 扩张仿真 → 统一 Markdown。

示例：
  PYTHONPATH=src .venv/bin/python scripts/run_yanfu_unified_analysis.py
  PYTHONPATH=src .venv/bin/python scripts/run_yanfu_unified_analysis.py --nav-csv data/nav.csv
"""

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
from yanfu_global_expansion.roadmap_report import build_executive_summary, write_executive_summary
from yanfu_global_expansion.universe_defaults import build_default_universe
from yanfu_v2_roadmap import (
    MarketMirror,
    build_pivot_timeline,
    render_v2_roadmap_dashboard,
    strategic_sharpness_demo,
)
from yanfu_global_research.harvest_one_shot import run_harvest_sync
from yanfu_global_research.pipeline import run_full_pipeline
from yanfu_unified.report_md import build_unified_report

async def _run_expansion(out: Path, days: int, seed: int, target_bn: float) -> None:
    universe = build_default_universe()
    bt = CrossMarketBacktester(universe, n_trading_days=days, seed=seed)
    await bt.ingest_synthetic_universe()
    result = bt.run_sync()
    out.mkdir(parents=True, exist_ok=True)
    mm = MarketMirror(seed=seed)
    mirror_result = mm.run(n_days=days)
    pivot = build_pivot_timeline(n_trading_days=days, seed=seed + 1)
    sharp = strategic_sharpness_demo(seed=seed + 2)
    render_v2_roadmap_dashboard(
        mirror_result,
        pivot,
        out / "yanfu_v2_roadmap_analysis.png",
        sharpness=sharp,
    )
    write_executive_summary(out / "Executive_Summary.md", build_executive_summary(result, target_aum_usd_bn=target_bn))
    (out / "expansion_sim_metrics.json").write_text(
        json.dumps(
            {
                "sharpes_by_sleeve": result.sharpes_by_sleeve,
                "sortino_core_global_blend": result.sortino_core,
                "sortino_with_crypto_booster": result.sortino_with_crypto,
                "beta_neutral_meta_sample": result.beta_neutral_meta,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Unified Yanfu analysis: real harvest + research + expansion sim.")
    p.add_argument("--base-dir", type=Path, default=ROOT / "outputs" / "yanfu_unified")
    p.add_argument("--manager", default="上海衍复投资管理有限公司")
    p.add_argument("--amac-max-pages", type=int, default=400)
    p.add_argument("--harvest-detail-delay", type=float, default=0.2)
    p.add_argument("--harvest-detail-concurrency", type=int, default=3)
    p.add_argument("--amac-concurrency", type=int, default=4, help="AMAC API parallel page fetches (lower if connection resets).")
    p.add_argument("--amac-page-sleep", type=float, default=0.12, help="Delay between AMAC page requests per worker.")
    p.add_argument(
        "--max-fund-details",
        type=int,
        default=None,
        metavar="N",
        help="Harvest only first N fund detail HTML pages (omit = all). Saves most wall time.",
    )
    p.add_argument(
        "--refresh-crawl",
        action="store_true",
        help="Bypass disk cache: refetch AMAC list, fund HTML, Yanfu pages; Research also refetches AMAC.",
    )
    p.add_argument("--skip-harvest", action="store_true")
    p.add_argument("--skip-research", action="store_true")
    p.add_argument("--skip-expansion", action="store_true")
    p.add_argument("--nav-csv", type=Path, default=None)
    p.add_argument(
        "--expansion-days",
        type=int,
        default=DEFAULT_SIMULATION_TRADING_DAYS,
        help=f"Monte Carlo horizon in sessions (default {DEFAULT_SIMULATION_TRADING_DAYS} ≈ 18 months).",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--target-aum-bn", type=float, default=5.0)
    args = p.parse_args()

    base = Path(args.base_dir)
    hdir = base / "harvest"
    rdir = base / "research"
    edir = base / "expansion"

    harvest_amac_json = hdir / "amac_funds_api_full.json"
    if not args.skip_harvest:
        hdir.mkdir(parents=True, exist_ok=True)
        run_harvest_sync(
            manager_name=args.manager,
            max_pages=args.amac_max_pages,
            out_dir=hdir,
            fund_detail_concurrency=args.harvest_detail_concurrency,
            fund_detail_delay_s=args.harvest_detail_delay,
            amac_concurrency=args.amac_concurrency,
            amac_page_sleep_s=args.amac_page_sleep,
            max_fund_details=args.max_fund_details,
            refresh_crawl=args.refresh_crawl,
        )

    if not args.skip_research:
        rdir.mkdir(parents=True, exist_ok=True)
        reuse_amac = (
            None
            if args.refresh_crawl
            else (harvest_amac_json if harvest_amac_json.is_file() else None)
        )
        run_full_pipeline(
            manager_name=args.manager,
            max_pages=args.amac_max_pages,
            page_sleep_s=args.amac_page_sleep,
            concurrency=args.amac_concurrency,
            out_dir=rdir,
            nav_csv=args.nav_csv,
            reuse_amac_json=reuse_amac,
            refresh_network_ingestion=args.refresh_crawl,
        )

    if not args.skip_expansion:
        edir.mkdir(parents=True, exist_ok=True)
        asyncio.run(
            _run_expansion(edir, days=args.expansion_days, seed=args.seed, target_bn=args.target_aum_bn)
        )

    base.mkdir(parents=True, exist_ok=True)
    report_body = build_unified_report(base)
    report_path = base / "Yanfu_Unified_Report.md"
    report_path.write_text(report_body, encoding="utf-8")

    print(report_path)
    print(base)


if __name__ == "__main__":
    main()
