#!/usr/bin/env python3
"""
拉取与「上海衍复投资管理有限公司」相关的公开信息（尽力而为）：

1. 基金业协会备案产品：分页扫描 amac-infodisc 的 /api/pof/fund，筛管理人名称。
2. 衍复官网「资讯信息」页：从 HTML 中解析公示公告标题（服务端已渲染部分列表）。
3. （可选）东方财富股东持股分析：若网络可达，尝试拉取示例 hdCode 对应接口。

说明：
- 私募证券产品通常不公开完整股票持仓；十大股东类披露仅覆盖部分场景。
- 依赖仅标准库；输出 JSON 到 stdout，并可写 --out。
- inferred_strategy_* 字段仅根据基金名称关键词启发式归类，非管理人官方策略说明。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MANAGER_NAME = "上海衍复投资管理有限公司"
AMAC_FUND_URL = "https://gs.amac.org.cn/amac-infodisc/api/pof/fund"
YANFU_CONSULT_URL = "https://yanfuinvestments.com/consult"
# 东方财富「股东持股分析」页常见 hdCode 示例（衍复价值一号相关，仅作探测；可能变更）
DEFAULT_EASTMONEY_HDCODE = "78188214"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _request_json(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def fetch_amac_funds_for_manager(
    manager_name: str,
    *,
    max_pages: int | None,
    sleep_s: float,
) -> dict[str, Any]:
    """分页拉取备案基金，筛出指定管理人。"""
    funds: list[dict[str, Any]] = []
    first = _request_json(
        AMAC_FUND_URL + "?rand=0.1&page=0&size=100",
        method="POST",
        data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    total_pages = int(first.get("totalPages") or 0)
    limit_pages = total_pages if max_pages is None else min(total_pages, max_pages)

    def take_page(page: int) -> list[dict[str, Any]]:
        if page == 0:
            return list(first.get("content") or [])
        time.sleep(sleep_s)
        j = _request_json(
            AMAC_FUND_URL + f"?rand=0.1&page={page}&size=100",
            method="POST",
            data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        return list(j.get("content") or [])

    for page in range(0, limit_pages):
        rows = take_page(page)
        for row in rows:
            if row.get("managerName") == manager_name:
                funds.append(
                    {
                        "fundName": row.get("fundName"),
                        "fundNo": row.get("fundNo"),
                        "workingState": row.get("workingState"),
                        "managerType": row.get("managerType"),
                        "putOnRecordDate": row.get("putOnRecordDate"),
                        "establishDate": row.get("establishDate"),
                        "mandatorName": row.get("mandatorName"),
                        "url": row.get("url"),
                    }
                )

    return {
        "source": "amac_pof_fund",
        "managerName": manager_name,
        "totalPagesReported": total_pages,
        "pagesScanned": limit_pages,
        "maxPagesCap": max_pages,
        "fundCount": len(funds),
        "funds": funds,
    }


def infer_strategy_hint(fund_name: str) -> dict[str, Any]:
    """
    根据备案基金全称做启发式策略归类（仅供参考，不构成投资建议）。
    """
    name = fund_name or ""
    tags: list[str] = []

    if re.search(r"指增|指数增强", name):
        tags.append("指增")
    if re.search(r"中性|对冲", name):
        tags.append("中性/对冲")
    if re.search(r"多元|多策略|混合", name) or "鲲鹏" in name:
        tags.append("多策略/混合(名称)")
    if re.search(r"FOF|母基金", name):
        tags.append("FOF")

    benchmarks: list[str] = []
    if "中证全指" in name:
        benchmarks.append("中证全指")
    if re.search(r"A500", name):
        benchmarks.append("中证A500")
    if "中证500" in name and "中证5000" not in name:
        benchmarks.append("中证500")
    if "中证1000" in name:
        benchmarks.append("中证1000")
    if "沪深300" in name:
        benchmarks.append("沪深300")
    if "小市值" in name:
        benchmarks.append("小市值")

    # 粗分类（互斥主标签）
    if re.search(r"指增|指数增强", name):
        category = "指数增强"
        bench = "+".join(benchmarks) if benchmarks else "未标明"
        summary = f"量化指数增强（基准倾向: {bench}）"
    elif re.search(r"中性|对冲", name):
        category = "市场中性/对冲"
        summary = "市场中性/对冲（名称暗示）"
    elif re.search(r"FOF|母基金", name):
        category = "FOF/配置"
        summary = "FOF/配置（名称暗示）"
    elif re.search(r"多元|多策略|混合", name) or "鲲鹏" in name:
        category = "多策略/混合"
        summary = "多策略/混合（名称暗示，需结合募集材料）"
    else:
        category = "其他"
        summary = "名称未标明典型指增/中性关键词，需结合募集材料"

    return {
        "inferred_category": category,
        "inferred_benchmarks": benchmarks,
        "inferred_benchmark_hint": "+".join(benchmarks) if benchmarks else "",
        "inferred_tags": tags,
        "inferred_summary": summary,
    }


def dedupe_funds_by_key(funds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str | None, str | None]] = set()
    out: list[dict[str, Any]] = []
    for row in funds:
        key = (row.get("fundName"), row.get("fundNo"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def enrich_funds_with_inference(funds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in funds:
        name = row.get("fundName") or ""
        hint = infer_strategy_hint(name)
        merged = {**row, **hint}
        enriched.append(merged)
    return enriched


def write_funds_csv(
    path: str,
    funds: list[dict[str, Any]],
    *,
    utf8_bom: bool,
) -> None:
    """导出便于 Excel 筛选的 CSV（已 enrich）。"""
    fieldnames = [
        "fundName",
        "fundNo",
        "workingState",
        "inferred_category",
        "inferred_benchmark_hint",
        "inferred_tags",
        "inferred_summary",
        "mandatorName",
        "establishDate",
        "putOnRecordDate",
    ]
    mode = "w"
    encoding = "utf-8-sig" if utf8_bom else "utf-8"
    with open(path, mode, encoding=encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in funds:
            tags = row.get("inferred_tags") or []
            w.writerow(
                {
                    "fundName": row.get("fundName", ""),
                    "fundNo": row.get("fundNo", ""),
                    "workingState": row.get("workingState", ""),
                    "inferred_category": row.get("inferred_category", ""),
                    "inferred_benchmark_hint": row.get("inferred_benchmark_hint", ""),
                    "inferred_tags": "|".join(tags),
                    "inferred_summary": row.get("inferred_summary", ""),
                    "mandatorName": row.get("mandatorName", ""),
                    "establishDate": row.get("establishDate", ""),
                    "putOnRecordDate": row.get("putOnRecordDate", ""),
                }
            )


def fetch_yanfu_consult_titles(html: str) -> list[dict[str, str]]:
    """从官网 consult 页 HTML 提取公告标题与日期（类名依赖站点，可能随改版失效）。"""
    entries: list[dict[str, str]] = []
    # 每条：month/year + title
    blocks = re.findall(
        r'page_mounth__Ekuay">(\d+/\d+)</div><div class="page_year__HezBk">(\d{4})</div>'
        r'.*?page_text__Q4HJb">([^<]+)</div>',
        html,
        re.DOTALL,
    )
    for m, y, title in blocks:
        entries.append({"date": f"{y}-{m.replace('/', '-')}", "title": title.strip()})
    return entries


def fetch_yanfu_consult() -> dict[str, Any]:
    req = urllib.request.Request(
        YANFU_CONSULT_URL,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    titles = fetch_yanfu_consult_titles(html)
    return {
        "source": "yanfu_official_consult",
        "url": YANFU_CONSULT_URL,
        "announcementCount": len(titles),
        "announcements": titles,
    }


def try_eastmoney_holder_sample(hd_code: str, timeout: float) -> dict[str, Any]:
    """尝试东方财富 datacenter 接口（字段名随站点调整，失败仅记录错误）。"""
    qs = urllib.parse.urlencode(
        {
            "sortColumns": "END_DATE",
            "sortTypes": "-1",
            "pageSize": 50,
            "pageNumber": 1,
            "reportName": "RPT_SHARE_HOLDER_ANN",
            "columns": "ALL",
            "filter": f'(HOLDER_ID="{hd_code}")',
        }
    )
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get?" + qs
    try:
        data = _request_json(url, timeout=timeout)
        return {
            "source": "eastmoney_datacenter_sample",
            "hdCode": hd_code,
            "ok": True,
            "rawKeys": list(data.keys()) if isinstance(data, dict) else None,
            "result": data,
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {
            "source": "eastmoney_datacenter_sample",
            "hdCode": hd_code,
            "ok": False,
            "error": str(e),
        }


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch public Yanfu-related fund/strategy info")
    p.add_argument(
        "--max-pages",
        type=int,
        default=400,
        help="AMAC 基金列表最多扫描页数（每页100条）；增大可提高完备性但更慢",
    )
    p.add_argument(
        "--all-pages",
        action="store_true",
        help="扫描协会报告的全部页数（可能很慢）",
    )
    p.add_argument("--sleep", type=float, default=0.12, help="AMAC 分页请求间隔（秒）")
    p.add_argument(
        "--eastmoney",
        action="store_true",
        help="尝试拉取东方财富示例股东接口（常因网络/接口变更失败）",
    )
    p.add_argument("--eastmoney-hdcode", default=DEFAULT_EASTMONEY_HDCODE)
    p.add_argument("--eastmoney-timeout", type=float, default=12.0)
    p.add_argument("-o", "--out", help="写入 JSON 文件路径")
    p.add_argument(
        "--csv",
        metavar="PATH",
        help="另存为 CSV（去重后、含 inferred_* 归类列）",
    )
    p.add_argument(
        "--csv-utf8-bom",
        action="store_true",
        help="CSV 使用 utf-8-sig，便于 Windows Excel 打开",
    )
    p.add_argument(
        "--no-dedupe",
        action="store_true",
        help="不去重基金行（默认按 fundName+fundNo 去重）",
    )
    args = p.parse_args()

    max_pages: int | None = None if args.all_pages else args.max_pages

    out: dict[str, Any] = {
        "manager": MANAGER_NAME,
        "notes": [
            "备案基金列表来自中国证券投资基金业协会公开接口；不构成投资建议。",
            "策略细节与完整持仓非公开材料，本脚本无法保证获取。",
            "inferred_* 字段由脚本根据基金名称关键词启发式生成，非管理人官方策略说明。",
        ],
    }

    try:
        amac_raw = fetch_amac_funds_for_manager(
            MANAGER_NAME,
            max_pages=max_pages,
            sleep_s=args.sleep,
        )
        rows = amac_raw.get("funds") or []
        raw_n = len(rows)
        if not args.no_dedupe:
            rows = dedupe_funds_by_key(rows)
        enriched = enrich_funds_with_inference(rows)
        amac_raw["funds"] = enriched
        amac_raw["fundCount"] = len(enriched)
        amac_raw["fundCountRawRows"] = raw_n
        amac_raw["dedupeApplied"] = not args.no_dedupe
        amac_raw["classification"] = "name_keyword_heuristic"
        out["amac"] = amac_raw
    except Exception as e:  # noqa: BLE001
        out["amac"] = {"error": str(e)}

    try:
        out["yanfu_site"] = fetch_yanfu_consult()
    except Exception as e:  # noqa: BLE001
        out["yanfu_site"] = {"error": str(e)}

    if args.eastmoney:
        out["eastmoney"] = try_eastmoney_holder_sample(
            args.eastmoney_hdcode,
            timeout=args.eastmoney_timeout,
        )
    else:
        out["eastmoney"] = {
            "skipped": True,
            "hint": "使用 --eastmoney 开启示例请求（易失败）",
        }

    text = json.dumps(out, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)

    if args.csv:
        funds = (out.get("amac") or {}).get("funds")
        if not isinstance(funds, list):
            raise SystemExit("无 amac.funds，无法写 CSV（请先修复拉取错误）")
        write_funds_csv(args.csv, funds, utf8_bom=args.csv_utf8_bom)


if __name__ == "__main__":
    main()
