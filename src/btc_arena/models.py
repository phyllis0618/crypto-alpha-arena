from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from alpha_arena.models import MacroRegimeSignal


class BTCMarketSnapshot(BaseModel):
    """Last price + 24h stats from CoinGlass (futures coins-markets + OHLC)."""

    symbol: str = "BTCUSDT"
    last_price: float = 0.0
    price_change_pct_24h: float = 0.0
    quote_volume_usd_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    fetched_at: Optional[datetime] = None
    source: str = "coinglass"
    error: Optional[str] = None


class CandleRow(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    volume_usd: float = 0.0


class MarketAnalytics(BaseModel):
    """Indicators from OHLCV (bar interval set by CoinGlass env)."""

    n_bars: int = 0
    volume_usd_last: float = 0.0
    volume_usd_sma_20: Optional[float] = None
    volume_ratio_vs_sma: Optional[float] = None
    realized_vol_short: Optional[float] = None
    rsi_14: Optional[float] = None
    high_low_range_pct_last: Optional[float] = None
    close_vs_typical_pct: Optional[float] = None


class CoinGlassEndpointCall(BaseModel):
    """One CoinGlass REST probe (for dashboard / debugging)."""

    name: str
    path: str
    ok: bool = False
    http_status: Optional[int] = None
    error: Optional[str] = None
    data_rows: Optional[int] = None
    preview: str = ""


class CoinGlassBTCContext(BaseModel):
    ok: bool = False
    error: Optional[str] = None
    funding_rate_avg: Optional[float] = None
    open_interest_usd: Optional[float] = None
    long_short_ratio: Optional[float] = None
    fear_greed: Optional[int] = None


class SocialXTweet(BaseModel):
    username: str
    text: str
    created_at: str = ""


class SocialXSnapshot(BaseModel):
    """Twitter / X API v2 (Bearer); optional."""

    ok: bool = False
    error: Optional[str] = None
    tweets: list[SocialXTweet] = Field(default_factory=list)
    note: str = ""


class UnifiedMarketSnapshot(BaseModel):
    """Single tick: everything the model sees (no future leakage)."""

    fetched_at: datetime
    market: BTCMarketSnapshot
    bar_interval: str = "4h"
    candles: list[CandleRow] = Field(default_factory=list)
    coinglass: CoinGlassBTCContext = Field(default_factory=CoinGlassBTCContext)
    analytics: MarketAnalytics = Field(default_factory=MarketAnalytics)
    coinglass_endpoints: list[CoinGlassEndpointCall] = Field(default_factory=list)
    macro: MacroRegimeSignal = Field(
        default_factory=lambda: MacroRegimeSignal(regime="neutral", reasoning="not loaded")
    )
    social: SocialXSnapshot = Field(default_factory=SocialXSnapshot)
    # Derived from last bars (names are generic; not necessarily 1m / 5m)
    ret_last_bar: float = 0.0
    ret_5bars: float = 0.0
    volume_usd_last_bar: float = 0.0


class Prediction(BaseModel):
    direction: Literal["UP", "DOWN", "FLAT"]
    confidence: float = Field(ge=0.0, le=1.0)
    pred_return_next: float = 0.0
    reasoning: str = ""
    model: str = "rules"


class SimulatedTrade(BaseModel):
    ts: datetime
    price: float
    direction: Literal["UP", "DOWN", "FLAT"]
    actual_return_next: float
    pnl_usd: float
    equity_after: float


class SimState(BaseModel):
    initial_cash: float = 10_000.0
    equity_usd: float = 10_000.0
    history: list[SimulatedTrade] = Field(default_factory=list)
