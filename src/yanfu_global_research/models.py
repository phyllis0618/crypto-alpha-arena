"""Strict Pydantic models for strategy DNA and validated time series."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class StrategyLabel(str, Enum):
    INDEX_ENHANCEMENT = "index_enhancement"
    MARKET_NEUTRAL = "market_neutral"
    SMALL_CAP_ALPHA = "small_cap_alpha"
    CTA = "cta"
    MULTI_STRATEGY = "multi_strategy"
    UNKNOWN = "unknown"


class BetaBenchmark(str, Enum):
    CSI_300 = "csi_300"
    CSI_500 = "csi_500"
    CSI_1000 = "csi_1000"
    CSI_ALL_SHARE = "csi_all_share"
    CSI_A500 = "csi_a500"
    SMALL_CAP_STYLE = "small_cap_style"
    NEUTRAL_BOOK = "neutral_book"
    UNKNOWN = "unknown"


class AlphaStyle(str, Enum):
    HIGH_TURNOVER = "high_turnover"
    LIQUIDITY_PROVISION = "liquidity_provision"
    STAT_ARB = "stat_arb"
    ALT_DATA_HEAVY = "alt_data_heavy"
    RETAIL_SENTIMENT = "retail_sentiment"
    SIZE_FACTOR_TILT = "size_factor_tilt"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class NavObservation(BaseModel):
    """Single NAV point (e.g. from fact sheet or allocator portal export)."""

    as_of: date
    nav: Annotated[float, Field(gt=0, description="Cumulative or unit NAV")]
    source: str = Field(..., min_length=1, description="e.g. amac_proxy, allocator_csv")

    @field_validator("as_of", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> date:
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            return date.fromisoformat(v[:10])
        raise TypeError("as_of must be date or ISO string")


class NavSeriesStats(BaseModel):
    """Validated performance statistics derived from NAV series."""

    observations: int = Field(ge=2)
    annualized_volatility: Optional[float] = Field(default=None, ge=0)
    annualized_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = Field(default=None, ge=0, le=1)
    annual_turnover_estimate: Optional[float] = Field(
        default=None,
        ge=0,
        description="Optional: from fact sheet; not inferred from NAV alone",
    )


class FundDNARecord(BaseModel):
    """One fund's scraped + engineered DNA."""

    fund_id: str = Field(..., description="Stable key, e.g. AMAC fundNo")
    fund_name: str = Field(..., min_length=2)
    manager_name: str = Field(default="上海衍复投资管理有限公司")
    working_state: Optional[str] = None
    custodian: Optional[str] = None
    strategy_labels: list[StrategyLabel] = Field(default_factory=list)
    primary_beta: BetaBenchmark = BetaBenchmark.UNKNOWN
    secondary_beta: list[BetaBenchmark] = Field(default_factory=list)
    alpha_styles: list[AlphaStyle] = Field(default_factory=list)
    nav_series: list[NavObservation] = Field(default_factory=list)
    performance: Optional[NavSeriesStats] = None
    data_provenance: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def align_performance_with_nav(self) -> FundDNARecord:
        if self.performance is not None and self.nav_series:
            if self.performance.observations != len(self.nav_series):
                raise ValueError("performance.observations must match len(nav_series)")
        return self


class StrategyDatabase(BaseModel):
    """Versioned JSON-serializable database."""

    version: str = Field(default="1.0.0")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(tz=None))
    manager: str = Field(default="上海衍复投资管理有限公司")
    funds: list[FundDNARecord]


class RegionalBenchmarkArchetype(BaseModel):
    region_code: str
    label: str
    archetype: str
    assumed_annual_turnover: float = Field(ge=0)
    assumed_sharpe_net: float
    factor_emphasis: list[str]
    liquidity_tier: str
    capacity_headroom_vs_us_large_cap: str


class GlobalBenchmarkPack(BaseModel):
    schema_version: int
    disclaimer: str
    regions: list[RegionalBenchmarkArchetype]
