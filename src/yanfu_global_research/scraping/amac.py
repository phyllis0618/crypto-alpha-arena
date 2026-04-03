"""Async AMAC private-fund listing ingestion (institutional-style paginator)."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import aiohttp

from yanfu_global_research.http_utils import create_connector, DEFAULT_UA, fetch_json_post

AMAC_FUND_URL = "https://gs.amac.org.cn/amac-infodisc/api/pof/fund"


async def fetch_amac_fund_page(
    session: aiohttp.ClientSession,
    page: int,
    *,
    size: int = 100,
) -> dict[str, Any]:
    url = f"{AMAC_FUND_URL}?rand=0.1&page={page}&size={size}"
    return await fetch_json_post(session, url, json_body={}, timeout=55.0, attempts=8)


async def collect_funds_for_manager(
    manager_name: str,
    *,
    max_pages: Optional[int],
    page_sleep_s: float = 0.12,
    concurrency: int = 4,
    full_api_row: bool = False,
) -> dict[str, Any]:
    """
    Concurrent page fetch with semaphore — mimics guarded ingestion pipelines.
    Lower default concurrency reduces ``Connection reset by peer`` from AMAC.
    """
    connector = create_connector(limit_per_host=max(6, concurrency * 2))
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": DEFAULT_UA}) as session:
        first = await fetch_amac_fund_page(session, 0)
        total_pages = int(first.get("totalPages") or 0)
        limit_pages = total_pages if max_pages is None else min(total_pages, max_pages)

        sem = asyncio.Semaphore(concurrency)
        page_payloads: dict[int, dict[str, Any]] = {0: first}

        async def load_page(page: int) -> None:
            async with sem:
                if page > 0 and page_sleep_s > 0:
                    await asyncio.sleep(page_sleep_s)
                page_payloads[page] = await fetch_amac_fund_page(session, page)

        await asyncio.gather(*(load_page(p) for p in range(1, limit_pages)))

        matched: list[dict[str, Any]] = []
        for p in range(limit_pages):
            for row in list(page_payloads[p].get("content") or []):
                if row.get("managerName") == manager_name:
                    if full_api_row:
                        rec = dict(row)
                        rec["_amacPage"] = p
                        matched.append(rec)
                    else:
                        matched.append(
                            {
                                "fundName": row.get("fundName"),
                                "fundNo": row.get("fundNo"),
                                "workingState": row.get("workingState"),
                                "managerType": row.get("managerType"),
                                "putOnRecordDate": row.get("putOnRecordDate"),
                                "establishDate": row.get("establishDate"),
                                "mandatorName": row.get("mandatorName"),
                                "managerName": row.get("managerName"),
                                "url": row.get("url"),
                                "_amacPage": p,
                            }
                        )

        return {
            "source": "amac_pof_fund_async",
            "managerName": manager_name,
            "totalPagesReported": total_pages,
            "pagesScanned": limit_pages,
            "maxPagesCap": max_pages,
            "fundCount": len(matched),
            "funds": matched,
        }


def run_amac_collection_sync(
    manager_name: str,
    *,
    max_pages: Optional[int] = 400,
    page_sleep_s: float = 0.08,
    concurrency: int = 8,
) -> dict[str, Any]:
    return asyncio.run(
        collect_funds_for_manager(
            manager_name,
            max_pages=max_pages,
            page_sleep_s=page_sleep_s,
            concurrency=concurrency,
            full_api_row=False,
        )
    )
