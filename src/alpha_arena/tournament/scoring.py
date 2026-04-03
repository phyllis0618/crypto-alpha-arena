from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np

from alpha_arena.config import settings


def max_drawdown_pct(equity_curve: Sequence[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd * 100.0


def sharpe_ratio(returns: Sequence[float], bars_per_year: float) -> float:
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0
    mu = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1))
    if sd < 1e-12:
        return 0.0
    raw = (mu / sd) * math.sqrt(bars_per_year)
    return max(-10.0, min(10.0, raw))


def sortino_ratio(returns: Sequence[float], bars_per_year: float) -> float:
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0
    mu = float(np.mean(arr))
    downside = arr[arr < 0]
    if downside.size < 2:
        dsd = float(np.std(arr, ddof=1))
    else:
        dsd = float(np.std(downside, ddof=1))
    if dsd < 1e-12:
        return 0.0
    raw = (mu / dsd) * math.sqrt(bars_per_year)
    return max(-10.0, min(10.0, raw))


def diversity_factors(
    tickers_this_step: Sequence[str],
    agent_ids: Sequence[str],
) -> dict[str, float]:
    c = Counter(t for t in tickers_this_step if t)
    factors: dict[str, float] = {}
    strength = settings.diversity_penalty_strength
    for aid, t in zip(agent_ids, tickers_this_step):
        k = c.get(t, 1)
        if k <= 1:
            factors[aid] = 1.0
        else:
            factors[aid] = 1.0 / (1.0 + strength * (k - 1))
    return factors


def composite_score(
    *,
    total_return: float,
    sharpe: float,
    sortino: float,
    max_dd_pct: float,
    diversity_factor: float,
) -> float:
    dd_penalty = max_dd_pct / 100.0
    return (
        0.35 * total_return
        + 0.25 * sharpe
        + 0.20 * sortino
        - 0.20 * dd_penalty
    ) * diversity_factor
