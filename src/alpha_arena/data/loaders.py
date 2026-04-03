from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from alpha_arena.models import (
    ExchangeFlowPoint,
    FundingPoint,
    OHLCVBar,
    OrderBookLevel,
    OrderBookSnapshot,
    SentimentSnapshot,
    WhaleEvent,
)


def load_ohlcv_csv(
    path: str | Path,
    ts_col: str = "timestamp",
    date_format: Optional[str] = None,
) -> list[OHLCVBar]:
    df = pd.read_csv(path)
    if date_format:
        df[ts_col] = pd.to_datetime(df[ts_col], format=date_format)
    else:
        df[ts_col] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.dropna(subset=[ts_col])
    out: list[OHLCVBar] = []
    for _, row in df.iterrows():
        ts = row[ts_col]
        if hasattr(ts, "to_pydatetime"):
            t = ts.to_pydatetime()
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        else:
            t = datetime.now(timezone.utc)
        out.append(
            OHLCVBar(
                ts=t,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
            )
        )
    return sorted(out, key=lambda b: b.ts)


def synthetic_l2(mid: float, depth: int = 5, tick_pct: float = 0.0001) -> OrderBookSnapshot:
    rng = np.random.default_rng()
    bids: list[OrderBookLevel] = []
    asks: list[OrderBookLevel] = []
    for i in range(depth):
        bp = mid * (1 - tick_pct * (i + 1))
        ap = mid * (1 + tick_pct * (i + 1))
        sz = float(rng.uniform(0.5, 5.0) * (depth - i))
        bids.append(OrderBookLevel(price=bp, size=sz))
        asks.append(OrderBookLevel(price=ap, size=sz))
    return OrderBookSnapshot(bids=bids, asks=asks, mid=mid)


def synthetic_funding(ticker: str, base_rate: float = 0.0001) -> FundingPoint:
    rng = np.random.default_rng()
    return FundingPoint(
        ticker=ticker,
        rate_8h=float(base_rate + rng.normal(0, 0.00005)),
    )


def placeholder_whales(ticker_base: str) -> list[WhaleEvent]:
    return [
        WhaleEvent(asset=ticker_base.split("/")[0], direction="out", notional_usd=2_000_000.0),
    ]


def placeholder_flows(ticker: str) -> list[ExchangeFlowPoint]:
    return [ExchangeFlowPoint(ticker=ticker, net_inflow_usd=-150_000.0)]


def placeholder_sentiment() -> SentimentSnapshot:
    rng = np.random.default_rng()
    return SentimentSnapshot(
        twitter_score=float(rng.uniform(-0.4, 0.4)),
        telegram_score=float(rng.uniform(-0.3, 0.3)),
    )
