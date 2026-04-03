"""Load illustrative global/regional archetypes (not firm disclosures)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from yanfu_global_research.models import GlobalBenchmarkPack


def load_reference_benchmarks(path: Optional[Path] = None) -> GlobalBenchmarkPack:
    if path is not None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return GlobalBenchmarkPack.model_validate(raw)
    here = Path(__file__).resolve().parent / "data" / "reference_benchmarks.json"
    raw = json.loads(here.read_text(encoding="utf-8"))
    return GlobalBenchmarkPack.model_validate(raw)
