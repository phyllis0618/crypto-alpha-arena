from __future__ import annotations

import math
from typing import Sequence

from btc_arena.models import CandleRow, MarketAnalytics


def _rsi(closes: Sequence[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    avg_g = gains / period
    avg_l = losses / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


def compute_market_analytics(candles: Sequence[CandleRow]) -> MarketAnalytics:
    """OHLCV-derived stats (volume in USD, momentum, volatility)."""
    if not candles:
        return MarketAnalytics()

    n = len(candles)
    closes = [c.close for c in candles]
    vols_usd = [c.volume_usd for c in candles]
    last = candles[-1]
    vol_last = vols_usd[-1]

    window = min(20, n)
    vol_sma = sum(vols_usd[-window:]) / window
    vol_ratio = vol_last / vol_sma if vol_sma > 0 else None

    rets: list[float] = []
    for i in range(1, n):
        if closes[i - 1] > 0:
            rets.append(closes[i] / closes[i - 1] - 1.0)
    rv20 = None
    if len(rets) >= 2:
        m = sum(rets[-window:]) / min(window, len(rets))
        var = sum((x - m) ** 2 for x in rets[-window:]) / max(1, min(window, len(rets)) - 1)
        rv20 = math.sqrt(var)

    rsi14 = _rsi(closes, 14)
    hl_range_pct = None
    if last.low > 0:
        hl_range_pct = (last.high - last.low) / last.low

    # Simple "typical price" vs close
    typ = (last.high + last.low + last.close) / 3.0
    close_vs_typical = (last.close / typ - 1.0) if typ > 0 else None

    return MarketAnalytics(
        n_bars=n,
        volume_usd_last=vol_last,
        volume_usd_sma_20=vol_sma,
        volume_ratio_vs_sma=vol_ratio,
        realized_vol_short=rv20,
        rsi_14=rsi14,
        high_low_range_pct_last=hl_range_pct,
        close_vs_typical_pct=close_vs_typical,
    )
