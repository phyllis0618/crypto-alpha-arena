from __future__ import annotations

from datetime import datetime, timezone

from btc_arena.models import Prediction, SimState, SimulatedTrade, UnifiedMarketSnapshot


def settle_previous(
    state: SimState,
    snap: UnifiedMarketSnapshot,
    prev_price: float,
    pending: Prediction,
) -> SimState:
    """One-step return realized; update paper PnL from prior prediction."""
    price = snap.market.last_price
    if price <= 0 or prev_price <= 0:
        return state
    actual = price / prev_price - 1.0
    w = 0.12 * pending.confidence
    if pending.direction == "FLAT":
        pnl = 0.0
    elif pending.direction == "UP":
        pnl = state.equity_usd * w * actual
    else:
        pnl = state.equity_usd * w * (-actual)

    eq = max(100.0, state.equity_usd + pnl)
    trade = SimulatedTrade(
        ts=datetime.now(timezone.utc),
        price=price,
        direction=pending.direction,
        actual_return_next=actual,
        pnl_usd=pnl,
        equity_after=eq,
    )
    h = list(state.history)
    h.append(trade)
    if len(h) > 500:
        h = h[-500:]
    return SimState(initial_cash=state.initial_cash, equity_usd=eq, history=h)
