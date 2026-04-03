from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"


class OrderIntent(BaseModel):
    """Legacy: direct order (optional / advanced)."""

    symbol: str = Field(..., description="e.g. BTCUSDT")
    side: Side
    notional_usd: float = Field(..., gt=0, description="Order size in USD at mark price")
    leverage: float = Field(default=1.0, ge=1.0, le=20.0)
    reduce_only: bool = False
    rationale: str = ""


class PricePrediction(BaseModel):
    """Forecast for **next** bar close vs current close: (close_{t+1}/close_t - 1)."""

    symbol: str
    pred_return_next: float = Field(
        ...,
        description="Predicted simple return for the upcoming step, e.g. 0.002 = +0.2%",
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    note: str = ""


class Fill(BaseModel):
    symbol: str
    side: Side
    qty: float
    price: float
    fee_usd: float
    agent_id: str
    step: int
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Position(BaseModel):
    symbol: str
    qty: float
    entry_price: float
    leverage: float = 1.0


class AgentAccount(BaseModel):
    agent_id: str
    name: str
    cash_usd: float
    positions: dict[str, Position] = Field(default_factory=dict)
    realized_pnl_usd: float = 0.0


class ArenaSnapshot(BaseModel):
    step: int
    prices: dict[str, float]
    accounts: dict[str, AgentAccount]
    recent_fills: list[Fill] = Field(default_factory=list)


class TickObservation(BaseModel):
    """Only past/current features — no future returns."""

    step: int
    symbol: str
    mid: float
    ret_1: float
    ret_5: float
    ret_20: float
    equity_usd: float
    cash_usd: float
    position_qty: float
    unrealized_pnl_usd: float


class PredictionLogRow(BaseModel):
    step: int
    agent_id: str
    symbol: str
    pred_return: float
    actual_return: float
    direction_hit: Optional[bool] = None
    step_pnl_usd: float


class LeaderboardRow(BaseModel):
    rank: int
    agent_id: str
    name: str
    equity_usd: float
    return_pct: float
    max_drawdown_pct: float
    direction_accuracy_pct: float = 0.0
    mae_return: float = 0.0


class SessionResult(BaseModel):
    meta: dict[str, Any]
    equity_curves: dict[str, list[tuple[int, float]]]
    fills: list[Fill]
    leaderboard: list[LeaderboardRow]
    prediction_logs: list[PredictionLogRow] = Field(default_factory=list)
