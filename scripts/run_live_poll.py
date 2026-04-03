#!/usr/bin/env python3
"""Standalone: only run CoinGlass + Macro poll loop (no FastAPI). Ctrl+C to stop."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from alpha_arena.live_feed import interval_from_env, live_feed_loop


async def main() -> None:
    interval = interval_from_env()
    print(f"Live poll every {interval}s — ensure .env has COINGLASS_API_KEY / FRED_API_KEY")
    await live_feed_loop(interval)


if __name__ == "__main__":
    asyncio.run(main())
