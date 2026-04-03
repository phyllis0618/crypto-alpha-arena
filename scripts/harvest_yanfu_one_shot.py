#!/usr/bin/env python3
"""One-off public harvest: AMAC API + fund detail pages + Yanfu.com + optional Simuwang snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from yanfu_global_research.harvest_one_shot import run_harvest_sync


def main() -> None:
    p = argparse.ArgumentParser(description="Harvest all reachable public Yanfu-related disclosures (one shot).")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "yanfu_one_shot_harvest",
        help="Output directory",
    )
    p.add_argument("--manager", default="上海衍复投资管理有限公司")
    p.add_argument("--max-pages", type=int, default=None, help="Cap AMAC fund list pages (default: all)")
    p.add_argument("--detail-concurrency", type=int, default=4)
    p.add_argument("--detail-delay", type=float, default=0.12, help="Per-request pacing inside each worker slot")
    p.add_argument("--no-yanfu-site", action="store_true")
    p.add_argument("--no-manager-page", action="store_true")
    p.add_argument("--no-simuwang", action="store_true")
    p.add_argument(
        "--max-fund-details",
        type=int,
        default=None,
        help="Only fetch first N fund detail pages (smoke test); default = all deduped funds",
    )
    p.add_argument(
        "--refresh-crawl",
        action="store_true",
        help="Ignore disk cache for AMAC list, fund HTML, Yanfu, manager, Simuwang snapshots.",
    )
    args = p.parse_args()

    manifest = run_harvest_sync(
        manager_name=args.manager,
        max_pages=args.max_pages,
        out_dir=args.out_dir,
        fund_detail_concurrency=args.detail_concurrency,
        fund_detail_delay_s=args.detail_delay,
        max_fund_details=args.max_fund_details,
        fetch_yanfu_site=not args.no_yanfu_site,
        fetch_amac_manager_page=not args.no_manager_page,
        fetch_simuwang_snapshot=not args.no_simuwang,
        refresh_crawl=args.refresh_crawl,
    )
    print(args.out_dir / "harvest_manifest.json")
    print(json.dumps(manifest.get("sources"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
