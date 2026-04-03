from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from alpha_arena.models import CoinGlassSnapshot

BASE = os.getenv("COINGLASS_API_BASE", "https://open-api-v4.coinglass.com").rstrip("/")
TIMEOUT = float(os.getenv("COINGLASS_TIMEOUT", "20"))


def _coinglass_success(j: dict[str, Any]) -> bool:
    """CoinGlass often returns HTTP 200 with JSON code '0' for success."""
    c = j.get("code")
    if c is None:
        return True
    if c in (0, "0", "00"):
        return True
    return False


def _coinglass_err_msg(j: dict[str, Any]) -> str:
    c = j.get("code")
    msg = j.get("msg") or j.get("message") or ""
    return f"CoinGlass API code={c} {msg}".strip()


def _pick_float(data: Any, *keys: str) -> float | None:
    cur: Any = data
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None


def _first_float(row: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


async def _fetch_coinglass_snapshot_with_client(
    client: httpx.AsyncClient, symbol: str
) -> CoinGlassSnapshot:
    now = datetime.now(timezone.utc)
    snap = CoinGlassSnapshot(symbol=symbol, fetched_at=now, ok=True)
    parts: list[str] = []

    # Aggregated futures coin stats (OI, funding, etc.)
    r1 = await client.get(f"{BASE}/api/futures/coins-markets")
    r1.raise_for_status()
    j1 = r1.json()
    if not _coinglass_success(j1):
        parts.append(_coinglass_err_msg(j1))
    data = j1.get("data")
    row: dict[str, Any] | None = None
    if isinstance(data, list):
        sym_u = symbol.upper()
        for item in data:
            if not isinstance(item, dict):
                continue
            if str(item.get("symbol", "")).upper() == sym_u or str(
                item.get("baseAsset", "")
            ).upper() == sym_u:
                row = item
                break
        if row is None and data and isinstance(data[0], dict):
            row = data[0]
    if row:
        snap.open_interest_usd = _pick_float(row, "openInterestUsd") or _pick_float(
            row, "openInterest", "usd"
        )
        snap.funding_rate_avg = _pick_float(row, "fundingRate") or _pick_float(
            row, "avgFundingRate"
        )
        snap.long_short_ratio = _pick_float(row, "longShortRatio")
        snap.liquidation_24h_usd = _pick_float(row, "liquidationUsd24h") or _pick_float(
            row, "liquidation24h"
        )
        snap.futures_price_usd = _first_float(
            row, "indexPrice", "markPrice", "price", "lastPrice"
        )
        snap.price_change_pct_24h = _first_float(
            row, "priceChangePercent24h", "priceChangePercent", "price_change_percent_24h"
        )
        snap.quote_volume_usd_24h = _first_float(
            row,
            "quoteVolumeUsd24h",
            "volumeUsd24h",
            "usdVolume24h",
            "volume24hUsd",
            "quoteVolume24h",
        )
        snap.high_24h_usd = _first_float(row, "high24h", "highPrice24h", "highPrice")
        snap.low_24h_usd = _first_float(row, "low24h", "lowPrice24h", "lowPrice")
        parts.append(str({k: row.get(k) for k in list(row.keys())[:12]}))

    r2 = await client.get(
        f"{BASE}/api/index/fear-greed-history",
        params={"limit": 1},
    )
    if r2.status_code == 200:
        j2 = r2.json()
        d2 = j2.get("data")
        if isinstance(d2, list) and d2 and isinstance(d2[0], dict):
            v = d2[0].get("value") or d2[0].get("fearGreed")
            if v is not None:
                try:
                    snap.fear_greed_value = int(float(v))
                except (TypeError, ValueError):
                    pass
            parts.append(f"fear_greed={d2[0]}")

    snap.raw_excerpt = " | ".join(parts)[:2000]
    return snap


async def _fetch_futures_ohlc_with_client(
    client: httpx.AsyncClient,
    exchange: str,
    symbol: str,
    interval: str,
    limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    lim = min(max(1, limit), 1000)
    max_retries = max(1, int(os.getenv("COINGLASS_OHLC_RETRIES", "5")))
    base_delay = float(os.getenv("COINGLASS_RETRY_DELAY_SEC", "1.25"))

    for attempt in range(max_retries):
        r = await client.get(
            f"{BASE}/api/futures/price/history",
            params={
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval,
                "limit": lim,
            },
        )
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            wait = float(ra) if ra and ra.isdigit() else min(60.0, base_delay * (2**attempt))
            await asyncio.sleep(wait)
            continue
        if r.status_code >= 400:
            return [], f"HTTP {r.status_code} price/history: {(r.text or '')[:220]}"

        j = r.json()
        if not _coinglass_success(j):
            err = _coinglass_err_msg(j)
            if str(j.get("code")) == "429" or "Too Many" in str(j.get("msg", "")):
                wait = min(60.0, base_delay * (2**attempt))
                await asyncio.sleep(wait)
                continue
            return [], err

        data = j.get("data")
        if not isinstance(data, list):
            return [], "no OHLC data in response (empty or unexpected shape)"
        out: list[dict[str, Any]] = []
        for x in data:
            if not isinstance(x, dict):
                continue
            try:
                t = int(x["time"])
                o = float(x["open"])
                h = float(x["high"])
                l = float(x["low"])
                c_ = float(x["close"])
                vol_usd = float(x.get("volume_usd") or 0.0)
                out.append(
                    {"time": t, "open": o, "high": h, "low": l, "close": c_, "volume_usd": vol_usd}
                )
            except (KeyError, TypeError, ValueError):
                continue
        out.sort(key=lambda b: b["time"])
        return out, None

    return [], (
        "CoinGlass rate limit (429): exhausted retries on /api/futures/price/history — "
        "wait 1–2 minutes, set COINGLASS_PROBE_MAX=0, and avoid bursting many endpoints."
    )


async def fetch_coinglass_snapshot(symbol: str = "BTC") -> CoinGlassSnapshot:
    """
    Pull live derivatives + sentiment context from CoinGlass Open API v4.
    Requires COINGLASS_API_KEY; otherwise returns ok=False with explanation.
    """
    key = os.getenv("COINGLASS_API_KEY", "").strip()
    now = datetime.now(timezone.utc)
    if not key:
        return CoinGlassSnapshot(
            symbol=symbol,
            fetched_at=now,
            ok=False,
            error="COINGLASS_API_KEY not set",
            raw_excerpt="Set COINGLASS_API_KEY in .env (header CG-API-KEY).",
        )

    headers = {"CG-API-KEY": key, "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            return await _fetch_coinglass_snapshot_with_client(client, symbol)
    except httpx.HTTPStatusError as e:
        return CoinGlassSnapshot(
            symbol=symbol,
            fetched_at=now,
            ok=False,
            error=f"http_{e.response.status_code}",
            raw_excerpt=(e.response.text or "")[:500],
        )
    except Exception as e:
        return CoinGlassSnapshot(
            symbol=symbol,
            fetched_at=now,
            ok=False,
            error=type(e).__name__,
            raw_excerpt=str(e)[:500],
        )


async def fetch_coinglass_btc_arena_bundle(
    symbol: str = "BTC",
) -> tuple[CoinGlassSnapshot, list[dict[str, Any]], str | None]:
    """
    One CoinGlass session: derivatives snapshot + futures OHLC (for BTC Arena).
    OHLC uses /api/futures/price/history (still CoinGlass; `exchange` selects venue feed).

    Returns (snapshot, ohlc_bars, ohlc_error).
    """
    key = os.getenv("COINGLASS_API_KEY", "").strip()
    now = datetime.now(timezone.utc)
    if not key:
        return (
            CoinGlassSnapshot(
                symbol=symbol,
                fetched_at=now,
                ok=False,
                error="COINGLASS_API_KEY not set",
                raw_excerpt="Set COINGLASS_API_KEY in .env (header CG-API-KEY).",
            ),
            [],
            "COINGLASS_API_KEY not set",
        )

    exchange = os.getenv("COINGLASS_FUTURES_EXCHANGE", "Binance").strip()
    pair = os.getenv("COINGLASS_FUTURES_SYMBOL", "BTCUSDT").strip()
    interval = os.getenv("COINGLASS_FUTURES_INTERVAL", "4h").strip()
    try:
        limit = int(os.getenv("COINGLASS_FUTURES_OHLC_LIMIT", "120"))
    except ValueError:
        limit = 120

    headers = {"CG-API-KEY": key, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            snap = await _fetch_coinglass_snapshot_with_client(client, symbol)
            try:
                bars, ohlc_err = await _fetch_futures_ohlc_with_client(
                    client, exchange, pair, interval, limit
                )
            except httpx.HTTPStatusError as e:
                bars, ohlc_err = [], f"ohlc_http_{e.response.status_code}"
            except Exception as e:
                bars, ohlc_err = [], f"ohlc_{type(e).__name__}"
            return snap, bars, ohlc_err
    except httpx.HTTPStatusError as e:
        err = f"http_{e.response.status_code}"
        return (
            CoinGlassSnapshot(
                symbol=symbol,
                fetched_at=now,
                ok=False,
                error=err,
                raw_excerpt=(e.response.text or "")[:500],
            ),
            [],
            err,
        )
    except Exception as e:
        err = type(e).__name__
        return (
            CoinGlassSnapshot(
                symbol=symbol,
                fetched_at=now,
                ok=False,
                error=err,
                raw_excerpt=str(e)[:500],
            ),
            [],
            str(e),
        )
