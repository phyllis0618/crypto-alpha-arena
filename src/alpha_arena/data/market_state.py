from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from alpha_arena.data.loaders import (
    placeholder_flows,
    placeholder_sentiment,
    placeholder_whales,
    synthetic_funding,
    synthetic_l2,
)
from alpha_arena.models import (
    AgentInfo,
    CoinGlassSnapshot,
    MacroRegimeSignal,
    MarketState,
    OHLCVBar,
    PortfolioState,
)


def build_market_state(
    *,
    step_index: int,
    ts: datetime,
    primary_ticker: str,
    bars_1m: Sequence[OHLCVBar],
    bars_5m: Sequence[OHLCVBar],
    portfolio: PortfolioState,
    interval: str = "1m",
    macro: MacroRegimeSignal | None = None,
    coinglass: CoinGlassSnapshot | None = None,
    agent_registry: list[AgentInfo] | None = None,
) -> MarketState:
    last = bars_1m[-1] if bars_1m else None
    mid = last.close if last else 0.0
    ob = synthetic_l2(mid) if mid > 0 else synthetic_l2(1.0)
    m = macro or MacroRegimeSignal()
    cg = coinglass or CoinGlassSnapshot()
    return MarketState(
        step_index=step_index,
        timestamp=ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc),
        interval=interval,  # type: ignore[arg-type]
        primary_ticker=primary_ticker,
        ohlcv_1m=list(bars_1m),
        ohlcv_5m=list(bars_5m),
        orderbook=ob,
        funding=[synthetic_funding(primary_ticker)],
        whale_events=placeholder_whales(primary_ticker),
        exchange_flows=placeholder_flows(primary_ticker),
        sentiment=placeholder_sentiment(),
        portfolio=portfolio,
        macro_regime=m.regime,
        macro_regime_confidence=m.confidence,
        macro_regime_reasoning=m.reasoning,
        coinglass=cg,
        agent_registry=list(agent_registry or []),
    )
