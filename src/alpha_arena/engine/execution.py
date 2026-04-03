from __future__ import annotations

import math
import random
from typing import Optional

from alpha_arena.config import settings
from alpha_arena.models import (
    MarketState,
    OpenPosition,
    PortfolioState,
    TradeAction,
    TradeExecutionResult,
)


def _slippage_bps(size_pct: float, volume: float) -> float:
    rng = random.Random()
    base = 2.0 + 40.0 * math.sqrt(max(size_pct, 1e-6))
    vol_factor = 1.0 / (1.0 + math.log1p(max(volume, 1.0)))
    jitter = rng.uniform(0.85, 1.15)
    return min(80.0, base * vol_factor * jitter)


def apply_fees(notional: float) -> float:
    return abs(notional) * (settings.taker_fee_bps / 10_000.0)


def _equity(cash: float, positions: list[OpenPosition], mark: float) -> float:
    u = 0.0
    for p in positions:
        u += p.qty * (mark - p.entry_price)
    return cash + u


def execute_action(
    *,
    agent_id: str,
    action: TradeAction,
    state: MarketState,
    portfolio: PortfolioState,
    mark_price: float,
    bar_volume: float,
) -> tuple[PortfolioState, TradeExecutionResult]:
    ticker = action.ticker.strip()
    if ticker not in settings.allowed_tickers:
        cash = portfolio.cash_usd - settings.failed_trade_penalty_usd
        eq = _equity(cash, list(portfolio.open_positions), mark_price)
        res = TradeExecutionResult(
            agent_id=agent_id,
            success=False,
            failed_reason=f"invalid_ticker:{ticker}",
            penalty_usd=settings.failed_trade_penalty_usd,
            pnl_delta_usd=-settings.failed_trade_penalty_usd,
        )
        return (
            portfolio.model_copy(update={"cash_usd": cash, "equity_usd": eq}),
            res,
        )

    if action.signal == "NEUTRAL":
        return portfolio, TradeExecutionResult(agent_id=agent_id, success=True, pnl_delta_usd=0.0)

    slip = _slippage_bps(action.execution.size_pct, bar_volume)
    side = 1.0 if action.signal == "LONG" else -1.0
    fill = mark_price * (1 + side * slip / 10_000.0)

    eq0 = max(_equity(portfolio.cash_usd, list(portfolio.open_positions), mark_price), 1.0)
    notional = eq0 * min(max(action.execution.size_pct, 0.0), 1.0) * max(action.confidence, 0.01)
    if notional < 1.0:
        return portfolio, TradeExecutionResult(agent_id=agent_id, success=True, pnl_delta_usd=0.0)

    qty_target = notional / fill * side

    positions = [p for p in portfolio.open_positions if p.ticker != ticker]
    cash = portfolio.cash_usd
    realized = 0.0
    fee_total = 0.0

    prev = next((p for p in portfolio.open_positions if p.ticker == ticker), None)
    if prev:
        realized += prev.qty * (fill - prev.entry_price)
        fee_total += apply_fees(abs(prev.qty) * fill)

    cash += realized
    cash -= fee_total

    qty = qty_target
    open_fee = apply_fees(abs(qty) * fill)
    cash -= qty * fill + open_fee

    new_pos = OpenPosition(
        ticker=ticker,
        side="LONG" if qty > 0 else "SHORT",
        qty=qty,
        entry_price=fill,
        notional_usd=abs(qty) * fill,
        take_profit=action.execution.take_profit,
        stop_loss=action.execution.stop_loss,
    )
    positions.append(new_pos)

    eq1 = _equity(cash, positions, mark_price)
    port = PortfolioState(
        cash_usd=cash,
        equity_usd=eq1,
        margin_used_usd=sum(abs(p.notional_usd) for p in positions),
        margin_available_usd=max(0.0, eq1 * 0.5),
        open_positions=positions,
    )
    res = TradeExecutionResult(
        agent_id=agent_id,
        success=True,
        fee_usd=fee_total + open_fee,
        slippage_bps=slip,
        pnl_delta_usd=eq1 - eq0,
    )
    return port, res


def mark_portfolio_to_market(portfolio: PortfolioState, mark_price: float) -> PortfolioState:
    eq = _equity(portfolio.cash_usd, list(portfolio.open_positions), mark_price)
    return portfolio.model_copy(update={"equity_usd": eq})


def check_tp_sl(portfolio: PortfolioState, mark_price: float) -> PortfolioState:
    cash = portfolio.cash_usd
    kept: list[OpenPosition] = []
    for p in portfolio.open_positions:
        hit = False
        if p.side == "LONG":
            if p.take_profit and mark_price >= p.take_profit:
                hit = True
            if p.stop_loss and mark_price <= p.stop_loss:
                hit = True
        else:
            if p.take_profit and mark_price <= p.take_profit:
                hit = True
            if p.stop_loss and mark_price >= p.stop_loss:
                hit = True
        if hit:
            pnl = p.qty * (mark_price - p.entry_price)
            cash += pnl
            cash -= apply_fees(abs(p.qty) * mark_price)
        else:
            kept.append(p)
    port = portfolio.model_copy(update={"cash_usd": cash, "open_positions": kept})
    return mark_portfolio_to_market(port, mark_price)
