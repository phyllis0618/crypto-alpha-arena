from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import requests


@dataclass
class Candle:
    step: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class SyntheticFeed:
    """GBM-style synthetic candles for offline demos."""

    def __init__(
        self,
        symbols: list[str],
        initial_prices: Optional[dict[str, float]] = None,
        seed: int = 42,
        dt_sigma: float = 0.012,
        dt_drift: float = 0.0,
    ) -> None:
        self.symbols = symbols
        rng = np.random.default_rng(seed)
        self._rng = rng
        self._dt_sigma = dt_sigma
        self._dt_drift = dt_drift
        init = initial_prices or {s: 100.0 for s in symbols}
        self._price = {s: float(init[s]) for s in symbols}
        self._history: dict[str, list[Candle]] = {s: [] for s in symbols}

    def step(self, t: int) -> dict[str, Candle]:
        out: dict[str, Candle] = {}
        for s in self.symbols:
            z = self._rng.normal()
            ret = self._dt_drift + self._dt_sigma * z
            o = self._price[s]
            c = max(1e-8, o * (1 + ret))
            h = max(o, c) * (1 + abs(self._rng.normal()) * 0.001)
            l = min(o, c) * (1 - abs(self._rng.normal()) * 0.001)
            vol = abs(self._rng.normal()) * 1e6
            candle = Candle(step=t, open=o, high=h, low=l, close=c, volume=vol)
            self._history[s].append(candle)
            self._price[s] = c
            out[s] = candle
        return out

    def closes(self, symbol: str, lookback: int) -> list[float]:
        hist = self._history.get(symbol, [])
        if not hist:
            return []
        return [c.close for c in hist[-lookback:]]


def fetch_binance_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 500,
) -> list[Candle]:
    """Public Binance spot klines (no API key). symbol e.g. BTCUSDT."""
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(
        url,
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=15,
    )
    r.raise_for_status()
    rows = r.json()
    candles: list[Candle] = []
    for i, row in enumerate(rows):
        o, h, low, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
        vol = float(row[5])
        candles.append(Candle(step=i, open=o, high=h, low=low, close=c, volume=vol))
    return candles


class ReplayFeed:
    """Replay preloaded candles and optionally loop."""

    def __init__(self, series: dict[str, list[Candle]], loop: bool = True) -> None:
        self._series = series
        self._loop = loop
        self.symbols = list(series.keys())
        self._idx = 0
        self._max_len = max(len(series[s]) for s in self.symbols)

    def step(self, t: int) -> dict[str, Candle]:
        out: dict[str, Candle] = {}
        for s in self.symbols:
            series = self._series[s]
            i = self._idx if self._idx < len(series) else len(series) - 1
            if self._loop and len(series) > 0:
                i = self._idx % len(series)
            c = series[i]
            out[s] = Candle(
                step=t,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
        self._idx += 1
        if self._idx >= self._max_len and not self._loop:
            pass
        return out

    def closes(self, symbol: str, lookback: int) -> list[float]:
        series = self._series.get(symbol, [])
        if not series:
            return []
        start = max(0, self._idx - lookback)
        return [c.close for c in series[start : self._idx]]


def build_feed_from_env(
    symbols: list[str],
    seed: int = 42,
) -> tuple[object, str]:
    """Return (feed, mode_label)."""
    if os.getenv("USE_BINANCE_FEED") == "1":
        series: dict[str, list[Candle]] = {}
        for s in symbols:
            series[s] = fetch_binance_klines(s, interval="1m", limit=300)
        return ReplayFeed(series, loop=True), "binance_replay"
    init = {"BTCUSDT": 95000.0, "ETHUSDT": 3500.0}
    prices = {k: init.get(k, 100.0) for k in symbols}
    return SyntheticFeed(symbols, initial_prices=prices, seed=seed), "synthetic"
