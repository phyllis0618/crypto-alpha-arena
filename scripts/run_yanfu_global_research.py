#!/usr/bin/env python3
"""CLI: async ingestion, Pydantic validation, gap analysis, Sharpe–turnover chart."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yanfu_global_research.pipeline import run_full_pipeline


def main() -> None:
    p = argparse.ArgumentParser(
        description="Yanfu DNA vs global multi-manager benchmark (research framework).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "yanfu_global_research",
        help="Output directory for JSON + PNG",
    )
    p.add_argument("--manager", default="上海衍复投资管理有限公司")
    p.add_argument("--max-pages", type=int, default=400)
    p.add_argument("--all-pages", action="store_true")
    p.add_argument("--page-sleep", type=float, default=0.08)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument(
        "--nav-csv",
        type=Path,
        help="Optional CSV columns: fund_no,as_of,nav[,source][,annual_turnover] — unlocks real Sharpe on chart",
    )
    p.add_argument("--benchmark-json", type=Path, help="Override reference archetypes JSON")
    p.add_argument(
        "--reuse-amac-json",
        type=Path,
        default=None,
        help="Skip AMAC list API if this path (e.g. harvest/amac_funds_api_full.json) is valid for --manager/--max-pages.",
    )
    p.add_argument(
        "--refresh-crawl",
        action="store_true",
        help="Force live AMAC list + Yanfu consult (ignore --reuse-amac-json).",
    )
    args = p.parse_args()

    max_pages = None if args.all_pages else args.max_pages
    reuse = None if args.refresh_crawl else args.reuse_amac_json
    paths = run_full_pipeline(
        manager_name=args.manager,
        max_pages=max_pages,
        page_sleep_s=args.page_sleep,
        concurrency=args.concurrency,
        nav_csv=args.nav_csv,
        benchmark_json=args.benchmark_json,
        out_dir=args.out_dir,
        reuse_amac_json=reuse,
        refresh_network_ingestion=args.refresh_crawl,
    )
    for k, v in paths.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
