"""
Stage 2-A — Biotech quantamental hooks (structured signals from non-structured sources).

Wire real NLP / trial DB here; this module holds the **contract** only.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ClinicalTrialFact(BaseModel):
    """One row after agentic extraction + QC."""

    symbol: str = Field(..., description="US listing / ADR")
    molecule_or_asset: Optional[str] = None
    trial_id: Optional[str] = None
    phase: Optional[str] = Field(None, description="1/2/3 or combined")
    p_value: Optional[float] = Field(None, ge=0.0, le=1.0)
    endpoint_met: Optional[bool] = None
    pdufa_date: Optional[date] = None
    pipeline_tier: Optional[str] = Field(None, description="e.g. priority_review / standard")
    source_doc_hash: Optional[str] = None
    confidence_0_1: float = Field(0.5, ge=0.0, le=1.0)


class BiotechAgentRunManifest(BaseModel):
    """Batch run metadata for audit."""

    run_id: str
    as_of: date
    facts_extracted: int = 0
    model_name: str = "placeholder"
    notes: str = "Replace with proprietary clinical NLP + structured FDA/SEC feeds."
