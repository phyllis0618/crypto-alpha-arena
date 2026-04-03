"""Serialize analysis artifacts for downstream systems."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from yanfu_global_research.analyzer import GapAnalysisReport


def gap_report_to_jsonable(report: GapAnalysisReport) -> dict[str, Any]:
    d = asdict(report)
    return d
