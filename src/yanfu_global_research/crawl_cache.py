"""Disk cache helpers for AMAC list + reuse between Harvest and Research pipelines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def harvest_json_to_amac_bundle(data: dict[str, Any]) -> dict[str, Any]:
    """Turn `harvest/amac_funds_api_full.json` into the dict shape expected by `build_database_from_amac`."""
    meta = data.get("meta") or {}
    funds = list(data.get("funds") or [])
    return {
        "source": meta.get("source", "amac_cached"),
        "managerName": meta.get("managerName", ""),
        "totalPagesReported": int(meta.get("totalPagesReported") or 0),
        "pagesScanned": int(meta.get("pagesScanned") or 0),
        "maxPagesCap": meta.get("maxPagesCap"),
        "fundCount": len(funds),
        "funds": funds,
    }


def amac_list_cache_covers_request(
    meta: dict[str, Any],
    *,
    manager_name: str,
    max_pages: Optional[int],
) -> bool:
    """Whether a cached AMAC list scan is sufficient for the requested manager + page cap."""
    if meta.get("managerName") != manager_name:
        return False
    total_reported = int(meta.get("totalPagesReported") or 0)
    pages_scanned = int(meta.get("pagesScanned") or 0)
    if total_reported <= 0 or pages_scanned <= 0:
        return False
    if max_pages is None:
        return pages_scanned >= total_reported
    need = min(int(max_pages), total_reported)
    return pages_scanned >= need


def try_read_amac_bundle_from_harvest_json(
    path: Path,
    *,
    manager_name: str,
    max_pages: Optional[int],
) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    meta = data.get("meta") or {}
    if not amac_list_cache_covers_request(meta, manager_name=manager_name, max_pages=max_pages):
        return None
    return harvest_json_to_amac_bundle(data)
