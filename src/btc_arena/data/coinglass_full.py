from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from alpha_arena.data.coinglass_client import (
    BASE,
    TIMEOUT,
    _coinglass_err_msg,
    _coinglass_success,
    _fetch_coinglass_snapshot_with_client,
    _fetch_futures_ohlc_with_client,
)
from alpha_arena.models import CoinGlassSnapshot
from btc_arena.models import CoinGlassEndpointCall


def _preview(data: Any, max_len: int = 420) -> str:
    try:
        if isinstance(data, (list, dict)):
            s = json.dumps(data, ensure_ascii=False)[:max_len]
        else:
            s = str(data)[:max_len]
    except Exception:
        s = str(data)[:max_len]
    return s + ("…" if len(s) >= max_len else "")


async def _probe(
    client: httpx.AsyncClient,
    name: str,
    path: str,
    params: dict[str, Any] | None,
) -> CoinGlassEndpointCall:
    try:
        r = await client.get(f"{BASE}{path}", params=params or {})
        status = r.status_code
        if status >= 400:
            return CoinGlassEndpointCall(
                name=name,
                path=path,
                ok=False,
                http_status=status,
                error=(r.text or "")[:220],
            )
        j = r.json()
        if not _coinglass_success(j):
            return CoinGlassEndpointCall(
                name=name,
                path=path,
                ok=False,
                http_status=status,
                error=_coinglass_err_msg(j)[:220],
            )
        data = j.get("data")
        rows = len(data) if isinstance(data, list) else (1 if data is not None else 0)
        preview_src = data if isinstance(data, (list, dict)) else j
        return CoinGlassEndpointCall(
            name=name,
            path=path,
            ok=True,
            http_status=status,
            data_rows=rows,
            preview=_preview(preview_src),
        )
    except Exception as e:
        return CoinGlassEndpointCall(name=name, path=path, ok=False, error=str(e)[:160])


def _endpoint_jobs(
    exchange: str, pair: str, interval: str, limit: int
) -> list[tuple[str, str, dict[str, Any] | None]]:
    lim = min(max(1, limit), 100)
    lim_s = str(lim)
    base_coin = "BTC"
    jobs: list[tuple[str, str, dict[str, Any] | None]] = [
        ("supported_coins", "/api/futures/supported-coins", {}),
        ("supported_exchanges", "/api/futures/supported-exchanges", {}),
        ("supported_pairs", "/api/futures/supported-exchange-pairs", {"exchange": exchange}),
        ("coins_price_change", "/api/futures/coins-price-change", {"limit": "30"}),
        ("exchange_rank", "/api/futures/exchange-rank", {"limit": "20"}),
        ("futures_spot_vol_ratio", "/api/futures_spot_volume_ratio", {"limit": "30"}),
        (
            "oi_history",
            "/api/futures/open-interest/history",
            {"exchange": exchange, "symbol": pair, "interval": interval, "limit": lim_s},
        ),
        (
            "oi_agg_history",
            "/api/futures/open-interest/aggregated-history",
            {"symbol": base_coin, "interval": interval, "limit": lim_s},
        ),
        (
            "funding_history",
            "/api/futures/funding-rate/history",
            {"exchange": exchange, "symbol": pair, "interval": interval, "limit": lim_s},
        ),
        (
            "liq_agg",
            "/api/futures/liquidation/aggregated-history",
            {"symbol": base_coin, "interval": interval, "limit": lim_s},
        ),
        (
            "taker_agg",
            "/api/futures/aggregated-taker-buy-sell-volume/history",
            {"symbol": base_coin, "interval": interval, "limit": lim_s},
        ),
        (
            "global_ls_ratio",
            "/api/futures/global-long-short-account-ratio/history",
            {"exchange": exchange, "symbol": pair, "interval": interval, "limit": lim_s},
        ),
        (
            "funding_by_exchange",
            "/api/futures/funding-rate/exchange-list",
            {"symbol": pair},
        ),
        ("fear_greed_hist", "/api/index/fear-greed-history", {"limit": "5"}),
        ("ahr999", "/api/index/ahr999", {"limit": "30"}),
        ("btc_dominance", "/api/index/bitcoin-dominance", {"limit": "30"}),
        ("etf_bitcoin_list", "/api/etf/bitcoin/list", {}),
        ("articles", "/api/article/list", {"limit": "10"}),
        ("netflow_list", "/api/futures/netflow-list", {"limit": "30"}),
        (
            "cvd_agg",
            "/api/futures/aggregated-cvd/history",
            {"symbol": base_coin, "interval": interval, "limit": lim_s},
        ),
    ]
    return jobs


async def fetch_btc_arena_coinglass_full(
    symbol: str = "BTC",
) -> tuple[CoinGlassSnapshot, list[dict[str, Any]], str | None, list[CoinGlassEndpointCall]]:
    """
    CoinGlass snapshot + OHLC + parallel probes across many documented endpoints.
    Failures are per-endpoint (still returns partial data).
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
            [],
        )

    exchange = os.getenv("COINGLASS_FUTURES_EXCHANGE", "Binance").strip()
    pair = os.getenv("COINGLASS_FUTURES_SYMBOL", "BTCUSDT").strip()
    interval = os.getenv("COINGLASS_FUTURES_INTERVAL", "4h").strip()
    try:
        limit = int(os.getenv("COINGLASS_FUTURES_OHLC_LIMIT", "120"))
    except ValueError:
        limit = 120

    # Default 0: extra probes burst CoinGlass quota (HTTP/JSON 429). Raise only when needed.
    max_probe = int(os.getenv("COINGLASS_PROBE_MAX", "0"))
    probe_delay = float(os.getenv("COINGLASS_PROBE_DELAY_SEC", "0.45"))
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

            jobs = _endpoint_jobs(exchange, pair, interval, limit)[: max(0, max_probe)]
            probes: list[CoinGlassEndpointCall] = []
            for j in jobs:
                await asyncio.sleep(probe_delay)
                probes.append(await _probe(client, j[0], j[1], j[2]))
            return snap, bars, ohlc_err, probes
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
            [],
        )
    except Exception as e:
        return (
            CoinGlassSnapshot(
                symbol=symbol,
                fetched_at=now,
                ok=False,
                error=type(e).__name__,
                raw_excerpt=str(e)[:500],
            ),
            [],
            str(e),
            [],
        )
