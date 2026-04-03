"""
一次性尽可能拉取「衍复 + 备案产品」相关的**公开**材料（非实时、可离线重复跑）。

包含：
- 基金业协会：产品列表 API（完整字段）+ 每只产品公示详情页表格解析
- 衍复官网：若干静态 HTML 页面原样保存
- （可选）协会管理人公示页：若列表里能解析出 manager 详情 id

不包含：净值、业绩、持仓（公开渠道通常不提供或需登录）。
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiohttp
from bs4 import BeautifulSoup

from yanfu_global_research.crawl_cache import try_read_amac_bundle_from_harvest_json
from yanfu_global_research.http_utils import DEFAULT_UA, create_connector, fetch_text
from yanfu_global_research.scraping.amac import AMAC_FUND_URL, collect_funds_for_manager

AMAC_FUND_DETAIL_TMPL = "https://gs.amac.org.cn/amac-infodisc/res/pof/fund/{page_id}.html"
AMAC_MANAGER_DETAIL_TMPL = "https://gs.amac.org.cn/amac-infodisc/res/pof/manager/{page_id}.html"

YANFU_PAGES = [
    "https://yanfuinvestments.com/",
    "https://yanfuinvestments.com/about",
    "https://yanfuinvestments.com/consult",
    "https://yanfuinvestments.com/join",
]

# 第三方公司介绍页（多为 SPA，保存的是首屏 HTML，不一定含基金列表 JSON）
SIMUWANG_COMPANY_PAGE = "https://dc.simuwang.com/company/CO00003EOW.html"

# 协会管理人公示页 id（若 API 行缺少 managerUrl 则回退；以协会网站为准，若改版需更新）
YANFU_AMAC_MANAGER_PAGE_ID_FALLBACK = "1908041900102948"


def _dedupe_funds_by_no(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        fn = str(r.get("fundNo") or "").strip()
        if not fn or fn in seen:
            continue
        seen.add(fn)
        out.append(r)
    return out


def parse_amac_fund_detail_table(html: str) -> dict[str, str]:
    """解析协会基金公示页 `td.title` + 值单元格。"""
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        c0 = tds[0].get("class") or []
        if "title" not in c0:
            continue
        key = tds[0].get_text(" ", strip=True).strip().rstrip(":")
        val = tds[1].get_text(" ", strip=True)
        if key:
            out[key] = val
    return out


def _page_id_from_fund_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    m = re.match(r"^(\d+)\.html$", str(url).strip())
    return m.group(1) if m else None


def _page_id_from_manager_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    s = str(url).strip()
    m = re.search(r"(\d+)\.html$", s)
    return m.group(1) if m else None


async def harvest_yanfu_one_shot(
    *,
    manager_name: str = "上海衍复投资管理有限公司",
    max_pages: Optional[int],
    out_dir: Path,
    fund_detail_concurrency: int = 3,
    fund_detail_delay_s: float = 0.2,
    amac_concurrency: int = 4,
    amac_page_sleep_s: float = 0.12,
    max_fund_details: Optional[int] = None,
    fetch_yanfu_site: bool = True,
    fetch_amac_manager_page: bool = True,
    fetch_simuwang_snapshot: bool = True,
    refresh_crawl: bool = False,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "manager": manager_name,
        "sources": [],
        "not_collected": [
            "Private fund NAV / time series performance (not in AMAC public API)",
            "Holdings, factor loadings, live book (proprietary)",
            "Simuwang 等站点上的结构化业绩/重仓需登录或其商业 API（此处仅保存首屏 HTML 快照）",
        ],
    }

    list_path = out_dir / "amac_funds_api_full.json"
    bundle: dict[str, Any]
    cached_amac = (
        None
        if refresh_crawl
        else try_read_amac_bundle_from_harvest_json(
            list_path,
            manager_name=manager_name,
            max_pages=max_pages,
        )
    )
    if cached_amac is not None:
        bundle = cached_amac
        manifest["_amac_list_source"] = "disk_cache_hit"
    else:
        bundle = await collect_funds_for_manager(
            manager_name,
            max_pages=max_pages,
            page_sleep_s=amac_page_sleep_s,
            concurrency=amac_concurrency,
            full_api_row=True,
        )
        manifest["_amac_list_source"] = "network"
    funds_raw: list[dict[str, Any]] = list(bundle.get("funds") or [])
    funds_deduped = _dedupe_funds_by_no(funds_raw)
    funds_for_details = funds_deduped if max_fund_details is None else funds_deduped[: max(0, max_fund_details)]

    if cached_amac is None:
        list_path.write_text(
            json.dumps(
                {
                    "meta": {k: bundle[k] for k in bundle if k != "funds"},
                    "fundCountDeduped": len(funds_deduped),
                    "funds": funds_deduped,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    manifest["sources"].append(
        {
            "id": "amac_pof_fund_api",
            "endpoint": AMAC_FUND_URL,
            "records": len(funds_deduped),
            "file": str(list_path.relative_to(out_dir)),
        }
    )

    manager_ids: set[str] = set()
    for r in funds_deduped:
        mid = _page_id_from_manager_url(r.get("managerUrl"))
        if mid:
            manager_ids.add(mid)
    if not manager_ids:
        manager_ids.add(YANFU_AMAC_MANAGER_PAGE_ID_FALLBACK)
        manifest["fallback_used"] = [
            "managerUrl missing on API rows; fetched known Yanfu AMAC manager page id fallback",
        ]
    if max_fund_details is not None:
        manifest["note"] = f"Fund detail crawl limited to first {len(funds_for_details)} of {len(funds_deduped)} deduped funds."

    connector = create_connector(limit_per_host=max(8, fund_detail_concurrency * 2))
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": DEFAULT_UA}) as session:
        sem = asyncio.Semaphore(fund_detail_concurrency)

        async def one_detail(row: dict[str, Any]) -> dict[str, Any]:
            page_id = _page_id_from_fund_url(row.get("url"))
            fund_no = row.get("fundNo")
            if not page_id:
                return {"fundNo": fund_no, "error": "no_url_page_id", "fields": {}}
            url = AMAC_FUND_DETAIL_TMPL.format(page_id=page_id)
            raw_fp = raw_dir / f"amac_fund_{page_id}.html"
            async with sem:
                if not refresh_crawl and raw_fp.is_file():
                    html = raw_fp.read_text(encoding="utf-8")
                    fields = parse_amac_fund_detail_table(html)
                    return {
                        "fundNo": fund_no,
                        "amacDetailUrl": url,
                        "pageId": page_id,
                        "fields": fields,
                        "_source": "disk_cache",
                    }
                await asyncio.sleep(fund_detail_delay_s)
                try:
                    html = await fetch_text(session, url, timeout=55.0, attempts=6)
                    raw_fp.write_text(html, encoding="utf-8")
                    fields = parse_amac_fund_detail_table(html)
                    return {"fundNo": fund_no, "amacDetailUrl": url, "pageId": page_id, "fields": fields}
                except Exception as e:  # noqa: BLE001
                    return {"fundNo": fund_no, "amacDetailUrl": url, "error": str(e), "fields": {}}

        detail_results = await asyncio.gather(*[one_detail(r) for r in funds_for_details])

        details_path = out_dir / "amac_fund_detail_parsed.json"
        details_path.write_text(json.dumps(detail_results, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["sources"].append(
            {
                "id": "amac_fund_html_detail",
                "records": len(detail_results),
                "parsed_file": str(details_path.relative_to(out_dir)),
                "raw_html_dir": str(raw_dir.relative_to(out_dir)),
            }
        )

        if fetch_yanfu_site:
            yanfu_saved: list[str] = []
            for yu in YANFU_PAGES:
                slug = re.sub(r"https?://[^/]+", "", yu).strip("/") or "home"
                fname = slug.replace("/", "_") + ".html"
                path = raw_dir / f"yanfu_{fname}"
                try:
                    if not refresh_crawl and path.is_file():
                        yanfu_saved.append(f"{str(path.relative_to(out_dir))} (cache)")
                        continue
                    html = await fetch_text(session, yu, timeout=35.0, attempts=5)
                    path.write_text(html, encoding="utf-8")
                    yanfu_saved.append(str(path.relative_to(out_dir)))
                except Exception as e:  # noqa: BLE001
                    yanfu_saved.append(f"FAILED:{yu}:{e}")
            manifest["sources"].append({"id": "yanfu_official_html", "files": yanfu_saved})

        if fetch_amac_manager_page and manager_ids:
            mgr_files: list[str] = []
            for mid in sorted(manager_ids):
                mgr_url = AMAC_MANAGER_DETAIL_TMPL.format(page_id=mid)
                fp = raw_dir / f"amac_manager_{mid}.html"
                try:
                    if not refresh_crawl and fp.is_file():
                        mgr_files.append(f"{str(fp.relative_to(out_dir))} (cache)")
                        continue
                    html = await fetch_text(session, mgr_url, timeout=55.0, attempts=6)
                    fp.write_text(html, encoding="utf-8")
                    mgr_files.append(str(fp.relative_to(out_dir)))
                except Exception as e:  # noqa: BLE001
                    mgr_files.append(f"FAILED:{mid}:{e}")
            manifest["sources"].append(
                {
                    "id": "amac_manager_html",
                    "manager_ids": sorted(manager_ids),
                    "files": mgr_files,
                }
            )
        elif fetch_amac_manager_page:
            manifest["sources"].append({"id": "amac_manager_html", "skipped": "no managerUrl in API rows"})

        if fetch_simuwang_snapshot:
            try:
                fp = raw_dir / "simuwang_company_CO00003EOW.html"
                if not refresh_crawl and fp.is_file():
                    manifest["sources"].append(
                        {
                            "id": "simuwang_company_snapshot",
                            "note": "SPA snapshot (disk cache)",
                            "file": str(fp.relative_to(out_dir)),
                        }
                    )
                else:
                    html = await fetch_text(session, SIMUWANG_COMPANY_PAGE, timeout=35.0, attempts=5)
                    fp.write_text(html, encoding="utf-8")
                    manifest["sources"].append(
                        {
                            "id": "simuwang_company_snapshot",
                            "note": "SPA snapshot only; structured fund data may require their API/login",
                            "file": str(fp.relative_to(out_dir)),
                        }
                    )
            except Exception as e:  # noqa: BLE001
                manifest["sources"].append({"id": "simuwang_company_snapshot", "error": str(e)})

    manifest_path = out_dir / "harvest_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def run_harvest_sync(
    *,
    manager_name: str = "上海衍复投资管理有限公司",
    max_pages: Optional[int] = None,
    out_dir: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    return asyncio.run(
        harvest_yanfu_one_shot(
            manager_name=manager_name,
            max_pages=max_pages,
            out_dir=out_dir,
            **kwargs,
        )
    )
