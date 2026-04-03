"""End-to-end ingestion → validation → analysis."""

from __future__ import annotations

import asyncio
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

from yanfu_global_research.analyzer import StrategyAnalyzer
from yanfu_global_research.benchmarks import load_reference_benchmarks
from yanfu_global_research.feature_engineering import build_fund_dna
from yanfu_global_research.models import FundDNARecord, StrategyDatabase
from yanfu_global_research.reporting import gap_report_to_jsonable
from yanfu_global_research.crawl_cache import try_read_amac_bundle_from_harvest_json
from yanfu_global_research.scraping import collect_funds_for_manager, scrape_yanfu_consult_public
from yanfu_global_research.realized_metrics import compute_realized_bundle
from yanfu_global_research.visualization import plot_comparison_dashboard


def _dedupe_funds(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        k = (str(r.get("fundNo") or ""), str(r.get("fundName") or ""))
        if k in seen or not k[0]:
            continue
        seen.add(k)
        out.append(r)
    return out


def load_nav_csv(
    path: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, float]]:
    """
    CSV columns: fund_no,as_of,nav[,source][,annual_turnover]

    If ``annual_turnover`` appears on any row for a fund, the last non-empty
    value is used as annual turnover (×/yr) for that fund's stats / chart.
    """
    by_fund: dict[str, list[dict[str, Any]]] = defaultdict(list)
    turnover_by_fund: dict[str, float] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = (row.get("fund_no") or row.get("fundNo") or "").strip()
            if not fid:
                continue
            as_of = date.fromisoformat(str(row["as_of"])[:10])
            nav = float(row["nav"])
            src = (row.get("source") or "allocator_csv").strip()
            by_fund[fid].append({"as_of": as_of, "nav": nav, "source": src})
            at = row.get("annual_turnover")
            if at is not None and str(at).strip() != "":
                turnover_by_fund[fid] = float(at)
    return dict(by_fund), turnover_by_fund


async def run_async_ingestion(
    manager_name: str,
    *,
    max_pages: Optional[int],
    page_sleep_s: float,
    concurrency: int,
    precooked_amac_bundle: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    async def _amac() -> dict[str, Any]:
        if precooked_amac_bundle is not None:
            return precooked_amac_bundle
        return await collect_funds_for_manager(
            manager_name,
            max_pages=max_pages,
            page_sleep_s=page_sleep_s,
            concurrency=concurrency,
        )

    amac_task = asyncio.create_task(_amac())
    yanfu_task = asyncio.create_task(scrape_yanfu_consult_public())
    amac, yanfu = await asyncio.gather(amac_task, yanfu_task)
    return {"amac": amac, "yanfu_site": yanfu}


def build_database_from_amac(
    amac_bundle: dict[str, Any],
    *,
    nav_by_fund: Optional[dict[str, list[dict[str, Any]]]] = None,
    turnover_by_fund: Optional[dict[str, float]] = None,
) -> StrategyDatabase:
    rows = _dedupe_funds(list(amac_bundle.get("funds") or []))
    funds: list[FundDNARecord] = []
    for r in rows:
        fid = str(r.get("fundNo"))
        nav_pts = None if not nav_by_fund else nav_by_fund.get(fid)
        at = None if not turnover_by_fund else turnover_by_fund.get(fid)
        funds.append(build_fund_dna(r, nav_points=nav_pts, turnover_annual_pct=at))
    return StrategyDatabase(funds=funds, manager=str(amac_bundle.get("managerName") or ""))


def run_full_pipeline(
    *,
    manager_name: str = "上海衍复投资管理有限公司",
    max_pages: Optional[int] = 400,
    page_sleep_s: float = 0.12,
    concurrency: int = 4,
    nav_csv: Optional[Path] = None,
    benchmark_json: Optional[Path] = None,
    out_dir: Path,
    reuse_amac_json: Optional[Path] = None,
    refresh_network_ingestion: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    nav_map: Optional[dict[str, list[dict[str, Any]]]] = None
    turnover_map: Optional[dict[str, float]] = None
    if nav_csv and nav_csv.exists():
        nav_map, turnover_map = load_nav_csv(nav_csv)

    precooked: Optional[dict[str, Any]] = None
    if (
        not refresh_network_ingestion
        and reuse_amac_json is not None
        and reuse_amac_json.is_file()
    ):
        precooked = try_read_amac_bundle_from_harvest_json(
            reuse_amac_json,
            manager_name=manager_name,
            max_pages=max_pages,
        )

    bundle = asyncio.run(
        run_async_ingestion(
            manager_name,
            max_pages=max_pages,
            page_sleep_s=page_sleep_s,
            concurrency=concurrency,
            precooked_amac_bundle=precooked,
        )
    )
    if precooked is not None and reuse_amac_json is not None:
        bundle["ingestion_note"] = {"amac_list": "reused_disk_json", "path": str(reuse_amac_json)}

    db = build_database_from_amac(
        bundle["amac"],
        nav_by_fund=nav_map,
        turnover_by_fund=turnover_map,
    )
    std = load_reference_benchmarks(benchmark_json)
    analyzer = StrategyAnalyzer(db, std)
    report = analyzer.gap_analysis()

    realized = compute_realized_bundle(db)
    realized_path = out_dir / "yanfu_realized_from_nav.json"
    realized_path.write_text(json.dumps(realized, indent=2, ensure_ascii=False), encoding="utf-8")

    db_path = out_dir / "yanfu_strategy_dna.json"
    db_path.write_text(db.model_dump_json(indent=2), encoding="utf-8")

    gap_path = out_dir / "gap_analysis_report.json"
    gap_path.write_text(json.dumps(gap_report_to_jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")

    raw_path = out_dir / "ingestion_raw.json"
    raw_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    chart_path = out_dir / "yanfu_comparison_dashboard.png"
    plot_comparison_dashboard(db, std, chart_path, realized=realized)

    return {
        "strategy_database": str(db_path),
        "gap_report": str(gap_path),
        "raw_ingestion": str(raw_path),
        "realized_from_nav": str(realized_path),
        "chart": str(chart_path),
    }
