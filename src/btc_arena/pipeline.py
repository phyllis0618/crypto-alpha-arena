from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import os

from dotenv import load_dotenv

from btc_arena.analytics import compute_market_analytics
from btc_arena.data.coinglass_full import fetch_btc_arena_coinglass_full
from alpha_arena.agents.macro_agent import MacroNewsAgent
from alpha_arena.models import CoinGlassSnapshot, MacroRegimeSignal
from btc_arena.data.coinglass_btc import coin_glass_context_from_snapshot
from btc_arena.data.social_x import fetch_social_x_snapshot
from btc_arena.models import (
    BTCMarketSnapshot,
    CandleRow,
    CoinGlassBTCContext,
    MarketAnalytics,
    Prediction,
    SimState,
    SocialXSnapshot,
    UnifiedMarketSnapshot,
)
from btc_arena.predictor import predict_single_model
from btc_arena.simulator import settle_previous


def _bars_to_candles(bars: list[dict[str, Any]]) -> list[CandleRow]:
    out: list[CandleRow] = []
    for b in bars:
        ts = datetime.fromtimestamp(b["time"] / 1000.0, tz=timezone.utc)
        close = b["close"]
        vol_usd = b["volume_usd"]
        vol_base = vol_usd / close if close > 0 else 0.0
        out.append(
            CandleRow(
                ts=ts,
                open=b["open"],
                high=b["high"],
                low=b["low"],
                close=close,
                volume=vol_base,
                volume_usd=vol_usd,
            )
        )
    return out


def _market_from_coinglass(
    snap: CoinGlassSnapshot,
    candles: list[CandleRow],
    ohlc_error: str | None,
) -> BTCMarketSnapshot:
    last = 0.0
    if candles:
        last = candles[-1].close
    elif snap.futures_price_usd is not None:
        last = snap.futures_price_usd

    pct_24 = snap.price_change_pct_24h
    if pct_24 is None and len(candles) >= 2:
        o0 = candles[0].open
        c1 = candles[-1].close
        if o0 and o0 > 0:
            pct_24 = (c1 / o0 - 1.0) * 100.0

    errs: list[str] = []
    if ohlc_error:
        errs.append(ohlc_error)
    if snap.error:
        errs.append(snap.error)

    return BTCMarketSnapshot(
        symbol="BTCUSDT",
        last_price=last,
        price_change_pct_24h=pct_24 or 0.0,
        quote_volume_usd_24h=snap.quote_volume_usd_24h or 0.0,
        high_24h=snap.high_24h_usd or 0.0,
        low_24h=snap.low_24h_usd or 0.0,
        fetched_at=snap.fetched_at,
        source="coinglass",
        error="; ".join(errs) if errs else None,
    )


async def _fetch_macro_safe(fear_greed: int | None) -> MacroRegimeSignal:
    """FRED DFF + SEC crypto headlines → risk_on / risk_off / neutral (same logic as Alpha Arena)."""
    try:
        return await MacroNewsAgent().compute_regime(fear_greed=fear_greed)
    except Exception as e:
        return MacroRegimeSignal(
            regime="neutral",
            reasoning=f"macro fetch failed: {e}",
            fed_note="",
        )


async def _build_snapshot_async() -> UnifiedMarketSnapshot:
    snap, bars, ohlc_err, probes = await fetch_btc_arena_coinglass_full("BTC")
    candles = _bars_to_candles(bars)
    cg = coin_glass_context_from_snapshot(snap)
    market = _market_from_coinglass(snap, candles, ohlc_err)
    analytics = compute_market_analytics(candles)

    ret_last = 0.0
    ret_5b = 0.0
    if len(candles) >= 2:
        ret_last = candles[-1].close / candles[-2].close - 1.0
    if len(candles) >= 6:
        ret_5b = candles[-1].close / candles[-6].close - 1.0

    vol_last = analytics.volume_usd_last if candles else 0.0

    bar_iv = os.getenv("COINGLASS_FUTURES_INTERVAL", "4h").strip()

    macro_sig, social_snap = await asyncio.gather(
        _fetch_macro_safe(cg.fear_greed),
        fetch_social_x_snapshot(),
    )

    return UnifiedMarketSnapshot(
        fetched_at=datetime.now(timezone.utc),
        market=market,
        bar_interval=bar_iv,
        candles=candles,
        coinglass=cg,
        analytics=analytics,
        coinglass_endpoints=probes,
        macro=macro_sig,
        social=social_snap,
        ret_last_bar=ret_last,
        ret_5bars=ret_5b,
        volume_usd_last_bar=vol_last,
    )


def build_snapshot() -> UnifiedMarketSnapshot:
    load_dotenv()
    try:
        return asyncio.run(_build_snapshot_async())
    except Exception as e:
        cg = CoinGlassBTCContext(ok=False, error=str(e))
        return UnifiedMarketSnapshot(
            fetched_at=datetime.now(timezone.utc),
            market=BTCMarketSnapshot(
                error=type(e).__name__,
                source="coinglass",
            ),
            coinglass=cg,
            analytics=MarketAnalytics(),
            coinglass_endpoints=[],
            macro=MacroRegimeSignal(regime="neutral", reasoning=str(e)),
            social=SocialXSnapshot(ok=False, error="pipeline_failed"),
        )


def run_pipeline_tick(
    state: SimState,
    prev_price: float | None,
    pending_prediction: Prediction | None,
) -> tuple[UnifiedMarketSnapshot, Prediction, SimState]:
    snap = build_snapshot()
    new_state = state
    if prev_price is not None and pending_prediction is not None:
        new_state = settle_previous(new_state, snap, prev_price, pending_prediction)

    pred = predict_single_model(snap)
    return snap, pred, new_state
