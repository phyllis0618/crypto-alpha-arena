from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from alpha_arena.models import CoinGlassSnapshot, LeaderboardEntry, MacroRegimeSignal

# Default: project root / outputs/


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_leaderboard_path() -> Path:
    env = os.getenv("ALPHA_ARENA_LEADERBOARD_JSON")
    if env:
        return Path(env).expanduser().resolve()
    return _repo_root() / "outputs" / "alpha_arena_leaderboard.json"


def default_live_context_path() -> Path:
    env = os.getenv("ALPHA_ARENA_LIVE_CONTEXT_JSON")
    if env:
        return Path(env).expanduser().resolve()
    return _repo_root() / "outputs" / "live_context.json"


def save_leaderboard_snapshot(
    entries: list[LeaderboardEntry],
    *,
    path: Path | None = None,
    meta: dict[str, Any] | None = None,
) -> Path:
    out = path or default_leaderboard_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "meta": meta or {},
        "leaderboard": [e.model_dump() for e in entries],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def load_leaderboard_snapshot(path: Path | None = None) -> list[LeaderboardEntry]:
    p = path or default_leaderboard_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        rows = data.get("leaderboard", [])
        return [LeaderboardEntry.model_validate(x) for x in rows]
    except Exception:
        return []


def save_live_context_snapshot(
    macro: MacroRegimeSignal,
    coinglass: CoinGlassSnapshot,
    *,
    trading_agents: list[dict[str, Any]],
    path: Path | None = None,
) -> Path:
    out = path or default_live_context_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "macro": macro.model_dump(mode="json"),
        "coinglass": coinglass.model_dump(mode="json"),
        "agents": trading_agents
        + [{"agent_id": "macro_news", "name": "Macro/News Agent", "role": "macro"}],
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def load_live_context_snapshot(path: Path | None = None) -> dict[str, Any]:
    p = path or default_live_context_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
