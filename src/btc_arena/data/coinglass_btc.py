from __future__ import annotations

import asyncio

from alpha_arena.data.coinglass_client import fetch_coinglass_btc_arena_bundle
from alpha_arena.models import CoinGlassSnapshot
from btc_arena.models import CoinGlassBTCContext


def coin_glass_context_from_snapshot(snap: CoinGlassSnapshot) -> CoinGlassBTCContext:
    return CoinGlassBTCContext(
        ok=snap.ok,
        error=snap.error,
        funding_rate_avg=snap.funding_rate_avg,
        open_interest_usd=snap.open_interest_usd,
        long_short_ratio=snap.long_short_ratio,
        fear_greed=snap.fear_greed_value,
    )


def run_coinglass_btc_sync() -> CoinGlassBTCContext:
    """Async CoinGlass client wrapped for Streamlit/sync callers."""

    async def _go() -> CoinGlassBTCContext:
        snap, _, _ = await fetch_coinglass_btc_arena_bundle("BTC")
        return coin_glass_context_from_snapshot(snap)

    return asyncio.run(_go())
