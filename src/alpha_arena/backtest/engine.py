from __future__ import annotations

import asyncio
from datetime import timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

from alpha_arena.agents.base import BaseAgent
from alpha_arena.data.loaders import load_ohlcv_csv
from alpha_arena.models import LeaderboardEntry, OHLCVBar
from alpha_arena.tournament.director import TournamentDirector


class BacktestEngine:
    """Replay OHLCV from CSV; optional callback after each calendar day."""

    def __init__(
        self,
        agents: Sequence[BaseAgent],
        *,
        initial_equity: float = 100_000.0,
        lookback_1m: int = 60,
        lookback_5m: int = 12,
    ) -> None:
        self.director = TournamentDirector(
            agents,
            initial_equity=initial_equity,
            enable_live=False,
        )
        self.lookback_1m = lookback_1m
        self.lookback_5m = lookback_5m
        self.daily_leaderboard_history: list[tuple[str, list[LeaderboardEntry]]] = []

    async def run_csv(
        self,
        path: str | Path,
        *,
        primary_ticker: str = "BTC/USDT",
        on_day_end: Optional[Callable[[str, list[LeaderboardEntry]], None]] = None,
    ) -> TournamentDirector:
        bars = load_ohlcv_csv(path)
        if not bars:
            return self.director

        def resample_5m(b1: list[OHLCVBar]) -> list[OHLCVBar]:
            if len(b1) < 5:
                return b1
            out: list[OHLCVBar] = []
            for i in range(0, len(b1), 5):
                chunk = b1[i : i + 5]
                if len(chunk) < 5:
                    break
                out.append(
                    OHLCVBar(
                        ts=chunk[-1].ts,
                        open=chunk[0].open,
                        high=max(x.high for x in chunk),
                        low=min(x.low for x in chunk),
                        close=chunk[-1].close,
                        volume=sum(x.volume for x in chunk),
                    )
                )
            return out if out else b1

        b5_full = resample_5m(bars)
        prev_day: Optional[str] = None

        for i, bar in enumerate(bars):
            ts = bar.ts if bar.ts.tzinfo else bar.ts.replace(tzinfo=timezone.utc)
            day = ts.strftime("%Y-%m-%d")
            w1 = bars[max(0, i - self.lookback_1m + 1) : i + 1]
            w5 = b5_full[-self.lookback_5m :] if b5_full else w1

            await self.director.run_step(
                step_index=i,
                ts=ts,
                bars_1m=w1,
                bars_5m=w5 if w5 else w1,
                primary_ticker=primary_ticker,
                mark_price=bar.close,
                bar_volume=bar.volume,
            )

            if prev_day is not None and day != prev_day and on_day_end:
                lb = list(self.director.last_leaderboard)
                self.daily_leaderboard_history.append((prev_day, lb))
                on_day_end(prev_day, lb)
            prev_day = day

        if on_day_end and prev_day is not None:
            lb = list(self.director.last_leaderboard)
            self.daily_leaderboard_history.append((prev_day, lb))
            on_day_end(prev_day, lb)

        return self.director


def run_backtest_sync(
    path: str | Path,
    agents: Sequence[BaseAgent],
    *,
    initial_equity: float = 100_000.0,
) -> TournamentDirector:
    eng = BacktestEngine(agents, initial_equity=initial_equity)

    async def _go() -> TournamentDirector:
        return await eng.run_csv(path)

    return asyncio.run(_go())
