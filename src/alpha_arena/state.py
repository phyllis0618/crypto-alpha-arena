from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from alpha_arena.tournament.director import TournamentDirector

_director: Optional[TournamentDirector] = None


def set_tournament_director(d: TournamentDirector) -> None:
    global _director
    _director = d


def get_tournament_director() -> Optional[TournamentDirector]:
    return _director


@dataclass
class LiveFeedState:
    """In-memory latest snapshot (API 轮询写入，优先于磁盘 JSON 展示)."""

    context: dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[datetime] = None
    last_error: Optional[str] = None
    poll_interval_sec: float = 60.0
    tick: int = 0


_live_feed = LiveFeedState()


def get_live_feed_state() -> LiveFeedState:
    return _live_feed


def set_live_context_cache(
    context: dict[str, Any],
    *,
    error: Optional[str] = None,
    poll_interval_sec: Optional[float] = None,
) -> None:
    global _live_feed
    _live_feed.context = context
    _live_feed.updated_at = datetime.now(timezone.utc)
    _live_feed.last_error = error
    _live_feed.tick += 1
    if poll_interval_sec is not None:
        _live_feed.poll_interval_sec = poll_interval_sec


def set_live_feed_error(msg: str) -> None:
    _live_feed.last_error = msg
