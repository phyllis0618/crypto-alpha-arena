"""Pydantic definitions for multi-market microstructure (illustrative roadmap simulation)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MarketMicrostructure(BaseModel):
    code: str = Field(..., description="Stable market sleeve code")
    name: str
    settlement: str = Field(..., description="e.g. T+0, T+1, T+2")
    retail_participation_pct: float = Field(..., ge=0, le=100)
    institutional_dominance_pct: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="If set, should align roughly with 100 - retail where applicable",
    )
    annualized_vol_hint: float = Field(..., gt=0, description="Illustrative cash equity / sleeve vol")
    impact_bps_per_million_notional: float = Field(
        ...,
        ge=0,
        description="Linear slippage anchor for capacity model (bps per $1M traded/day style scale)",
    )
    correlation_to_cn_alpha: float = Field(
        default=0.0,
        ge=-1,
        le=1,
        description="Target correlation of sleeve alpha to CN A-share reversal sleeve (simulation prior)",
    )
    momentum_reversal_alpha_transfer: float = Field(
        ...,
        ge=0,
        le=1,
        description="Relative transfer score for small-cap / reversal DNA vs CN baseline",
    )
    notes: str = ""


class GlobalMarketUniverse(BaseModel):
    """Distinct microstructure sleeves used in the expansion simulation (default path length ≈ 18 months)."""

    markets: dict[str, MarketMicrostructure]

    def by_code(self, code: str) -> MarketMicrostructure:
        return self.markets[code]

    model_config = {"frozen": False}
