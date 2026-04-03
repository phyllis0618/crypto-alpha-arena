from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from alpha_arena.data.live_context import fetch_macro_and_coinglass
from alpha_arena.models import CoinGlassSnapshot, MacroRegimeSignal
from alpha_arena.persistence import save_live_context_snapshot
from alpha_arena.state import set_live_context_cache, set_live_feed_error

logger = logging.getLogger("alpha_arena.live_feed")

DEFAULT_TRADING_AGENTS: list[dict[str, Any]] = [
    {"agent_id": "h1", "name": "Momentum-A", "role": "trading"},
    {"agent_id": "h2", "name": "Momentum-B", "role": "trading"},
    {"agent_id": "h3", "name": "Momentum-C", "role": "trading"},
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(_repo_root() / ".env")


async def poll_live_once(
    *,
    trading_agents: list[dict[str, Any]] | None = None,
    symbol: str = "BTC",
    poll_interval_sec: float = 60.0,
) -> dict[str, Any]:
    """一次完整拉取：CoinGlass + Macro → 落盘 + 内存缓存。"""
    agents = trading_agents or DEFAULT_TRADING_AGENTS
    try:
        macro, cg = await fetch_macro_and_coinglass(symbol)
    except Exception as e:
        logger.exception("live poll failed")
        macro = MacroRegimeSignal(regime="neutral", reasoning=f"fetch_error:{e!s}")
        cg = CoinGlassSnapshot(ok=False, error=str(e))

    save_live_context_snapshot(macro, cg, trading_agents=agents)
    payload = {
        "macro": macro.model_dump(mode="json"),
        "coinglass": cg.model_dump(mode="json"),
        "agents": agents
        + [{"agent_id": "macro_news", "name": "Macro/News Agent", "role": "macro"}],
        "meta": {
            "symbol": symbol,
            "source": "live_poll",
        },
    }
    set_live_context_cache(payload, error=None, poll_interval_sec=poll_interval_sec)
    return payload


async def live_feed_loop(interval_sec: float) -> None:
    """后台循环：启动后立即跑一轮，之后每 interval_sec 秒拉一次。"""
    load_env()
    while True:
        try:
            await poll_live_once(poll_interval_sec=interval_sec)
            logger.info("live poll ok (interval=%ss)", interval_sec)
        except Exception as e:
            logger.exception("live_feed_loop tick failed: %s", e)
            set_live_feed_error(str(e))
        await asyncio.sleep(interval_sec)


def interval_from_env() -> float:
    return float(os.getenv("LIVE_POLL_INTERVAL_SEC", "45"))
