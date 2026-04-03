from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


class OHLCVBar(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class OrderBookLevel(BaseModel):
    price: float
    size: float


class OrderBookSnapshot(BaseModel):
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    mid: float = 0.0


class FundingPoint(BaseModel):
    ticker: str
    rate_8h: float
    next_funding_ts: Optional[datetime] = None


class WhaleEvent(BaseModel):
    chain: str = "placeholder"
    asset: str
    direction: Literal["in", "out", "unknown"] = "unknown"
    notional_usd: float = 0.0
    label: str = "synthetic_whale"


class ExchangeFlowPoint(BaseModel):
    exchange: str = "aggregate"
    ticker: str
    net_inflow_usd: float = 0.0


class SentimentSnapshot(BaseModel):
    twitter_score: float = Field(0.0, ge=-1.0, le=1.0)
    telegram_score: float = Field(0.0, ge=-1.0, le=1.0)
    source: str = "placeholder_aggregate"


MarketRegime = Literal["risk_on", "risk_off", "neutral"]


class MacroRegimeSignal(BaseModel):
    """Output of Macro/News Agent — global input for trading agents."""

    regime: MarketRegime = "neutral"
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    fed_effective_rate_pct: Optional[float] = None
    fed_note: str = ""
    sec_crypto_headline_sample: str = ""
    sources: list[str] = Field(default_factory=list)


class CoinGlassSnapshot(BaseModel):
    """Latest CoinGlass-derived fields (read-only; no trading)."""

    symbol: str = "BTC"
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ok: bool = False
    error: Optional[str] = None
    funding_rate_avg: Optional[float] = None
    open_interest_usd: Optional[float] = None
    long_short_ratio: Optional[float] = None
    liquidation_24h_usd: Optional[float] = None
    fear_greed_value: Optional[int] = None
    # From futures coins-markets row (when present)
    futures_price_usd: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    quote_volume_usd_24h: Optional[float] = None
    high_24h_usd: Optional[float] = None
    low_24h_usd: Optional[float] = None
    raw_excerpt: str = ""


class AgentInfo(BaseModel):
    """Registry entry for dashboard."""

    agent_id: str
    name: str
    role: Literal["trading", "macro"] = "trading"


class OpenPosition(BaseModel):
    ticker: str
    side: Literal["LONG", "SHORT"]
    qty: float
    entry_price: float
    notional_usd: float
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None


class PortfolioState(BaseModel):
    cash_usd: float
    equity_usd: float
    margin_used_usd: float = 0.0
    margin_available_usd: float = 0.0
    open_positions: list[OpenPosition] = Field(default_factory=list)


class MarketState(BaseModel):
    """Unified view passed to every agent each turn."""

    step_index: int
    timestamp: datetime
    interval: Literal["1m", "5m"] = "1m"
    primary_ticker: str = "BTC/USDT"

    ohlcv_1m: list[OHLCVBar] = Field(default_factory=list)
    ohlcv_5m: list[OHLCVBar] = Field(default_factory=list)
    orderbook: OrderBookSnapshot = Field(default_factory=OrderBookSnapshot)
    funding: list[FundingPoint] = Field(default_factory=list)

    whale_events: list[WhaleEvent] = Field(default_factory=list)
    exchange_flows: list[ExchangeFlowPoint] = Field(default_factory=list)
    sentiment: SentimentSnapshot = Field(default_factory=SentimentSnapshot)

    portfolio: PortfolioState

    # Global regime (Macro/News Agent) + live derivatives context (CoinGlass)
    macro_regime: MarketRegime = "neutral"
    macro_regime_confidence: float = Field(0.5, ge=0.0, le=1.0)
    macro_regime_reasoning: str = ""

    coinglass: CoinGlassSnapshot = Field(default_factory=CoinGlassSnapshot)

    # Optional agent roster for UI / logging
    agent_registry: list[AgentInfo] = Field(default_factory=list)


class ExecutionBlock(BaseModel):
    type: Literal["MARKET", "LIMIT"]
    size_pct: float = Field(..., ge=0.0, le=1.0)
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None


class TradeAction(BaseModel):
    ticker: str
    signal: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = ""
    execution: ExecutionBlock


class TradeExecutionResult(BaseModel):
    agent_id: str
    success: bool
    failed_reason: Optional[str] = None
    fee_usd: float = 0.0
    slippage_bps: float = 0.0
    pnl_delta_usd: float = 0.0
    penalty_usd: float = 0.0


class AgentMetrics(BaseModel):
    agent_id: str
    name: str
    equity_usd: float
    peak_equity_usd: float
    returns: list[float] = Field(default_factory=list)
    liquidated: bool = False


class LeaderboardEntry(BaseModel):
    agent_id: str
    name: str
    equity_usd: float
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    diversity_factor: float = 1.0
    score: float
