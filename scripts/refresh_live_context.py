#!/usr/bin/env python3
"""Refresh Macro + CoinGlass JSON for the FastAPI dashboard (no backtest)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from alpha_arena.data.live_context import fetch_macro_and_coinglass
from alpha_arena.models import CoinGlassSnapshot, MacroRegimeSignal
from alpha_arena.persistence import default_live_context_path, save_live_context_snapshot


async def main() -> None:
    try:
        macro, cg = await fetch_macro_and_coinglass("BTC")
    except Exception as e:
        macro = MacroRegimeSignal(regime="neutral", reasoning=str(e))
        cg = CoinGlassSnapshot(ok=False, error=str(e))
    p = save_live_context_snapshot(
        macro,
        cg,
        trading_agents=[
            {"agent_id": "h1", "name": "Momentum-A", "role": "trading"},
            {"agent_id": "h2", "name": "Momentum-B", "role": "trading"},
            {"agent_id": "h3", "name": "Momentum-C", "role": "trading"},
        ],
    )
    print(json.dumps({"saved": str(p), "macro": macro.model_dump(), "coinglass_ok": cg.ok}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
