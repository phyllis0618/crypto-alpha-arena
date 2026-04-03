from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from btc_arena.models import BTCMarketSnapshot, CandleRow

DEFAULT_BASE = os.getenv("BINANCE_API_BASE", "https://api.binance.com").rstrip("/")


def _get(path: str, params: dict[str, Any]) -> requests.Response:
    return requests.get(f"{DEFAULT_BASE}{path}", params=params, timeout=15)


def fetch_btc_24h() -> BTCMarketSnapshot:
    try:
        r = _get("/api/v3/ticker/24hr", {"symbol": "BTCUSDT"})
        r.raise_for_status()
        d: dict[str, Any] = r.json()
        return BTCMarketSnapshot(
            symbol="BTCUSDT",
            last_price=float(d["lastPrice"]),
            price_change_pct_24h=float(d["priceChangePercent"]),
            quote_volume_usd_24h=float(d["quoteVolume"]),
            high_24h=float(d["highPrice"]),
            low_24h=float(d["lowPrice"]),
            fetched_at=datetime.now(timezone.utc),
            source="binance",
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (451, 403):
            return _fallback_coin_gecko_451()
        return BTCMarketSnapshot(
            error=f"binance:{e!s}",
            fetched_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        return BTCMarketSnapshot(
            error=str(e),
            fetched_at=datetime.now(timezone.utc),
        )


def _fallback_coin_gecko_451() -> BTCMarketSnapshot:
    """When Binance blocks region (HTTP 451), use CoinGecko public demo price."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=15,
        )
        r.raise_for_status()
        d = r.json()["bitcoin"]
        price = float(d["usd"])
        ch = float(d.get("usd_24h_change", 0.0))
        return BTCMarketSnapshot(
            symbol="BTCUSDT",
            last_price=price,
            price_change_pct_24h=ch,
            quote_volume_usd_24h=0.0,
            high_24h=price,
            low_24h=price,
            fetched_at=datetime.now(timezone.utc),
            source="coingecko_fallback",
            error="binance_unavailable_451_using_coingecko_spot_price",
        )
    except Exception as e:
        return BTCMarketSnapshot(
            error=f"binance_451_and_coingecko_failed:{e!s}",
            fetched_at=datetime.now(timezone.utc),
        )


def fetch_btc_klines_1m(limit: int = 120, *, fallback_price: float = 95000.0) -> list[CandleRow]:
    try:
        r = _get(
            "/api/v3/klines",
            {"symbol": "BTCUSDT", "interval": "1m", "limit": limit},
        )
        r.raise_for_status()
        rows: list[CandleRow] = []
        for x in r.json():
            ts = datetime.fromtimestamp(x[0] / 1000.0, tz=timezone.utc)
            rows.append(
                CandleRow(
                    ts=ts,
                    open=float(x[1]),
                    high=float(x[2]),
                    low=float(x[3]),
                    close=float(x[4]),
                    volume=float(x[5]),
                )
            )
        return rows
    except Exception:
        return _fallback_klines_synthetic(fallback_price, limit)


def _fallback_klines_synthetic(p: float, n: int) -> list[CandleRow]:
    """Last resort: flat synthetic path so UI still runs."""
    now = datetime.now(timezone.utc)
    out: list[CandleRow] = []
    for i in range(n):
        t = now.timestamp() - (n - i) * 60
        ts = datetime.fromtimestamp(t, tz=timezone.utc)
        out.append(
            CandleRow(ts=ts, open=p, high=p, low=p, close=p, volume=0.0)
        )
    return out
