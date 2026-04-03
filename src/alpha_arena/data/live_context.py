from __future__ import annotations

import asyncio

from alpha_arena.agents.macro_agent import MacroNewsAgent
from alpha_arena.data.coinglass_client import fetch_coinglass_snapshot
from alpha_arena.models import CoinGlassSnapshot, MacroRegimeSignal


async def fetch_macro_and_coinglass(symbol: str = "BTC") -> tuple[MacroRegimeSignal, CoinGlassSnapshot]:
    """Concurrent live fetch: CoinGlass (for F&G) + Macro/News regime."""
    cg_task = asyncio.create_task(fetch_coinglass_snapshot(symbol))
    cg = await cg_task
    fg = cg.fear_greed_value
    macro = MacroNewsAgent()
    regime = await macro.compute_regime(fear_greed=fg)
    return regime, cg
