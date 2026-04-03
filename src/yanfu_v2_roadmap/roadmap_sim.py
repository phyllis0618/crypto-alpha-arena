"""18-month pivot simulation: SEA cash-cow → US Special Ops (synthetic; ~378 sessions)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PivotTimelineResult:
    equity_curve: np.ndarray
    weight_sea: np.ndarray
    daily_returns: np.ndarray
    stage1_end_day: int
    stage2_ramp_end_day: int
    trading_days: int


DEFAULT_V2_TRADING_DAYS = 378  # ~18 months at ~21 sessions/month × 18

def build_pivot_timeline(
    *,
    n_trading_days: int = DEFAULT_V2_TRADING_DAYS,
    seed: int = 42,
    stage1_months: int = 6,
    ramp_end_months: int = 12,
    trading_days_per_month: int = 21,
) -> PivotTimelineResult:
    """
    ~18m horizon (default 378 days): 0–6m SEA-heavy → 6–12m glide to US ops → 12–18m plateau.

    Uses **illustrative** return streams (not live ETF data).
    """
    rng = np.random.default_rng(seed)
    d1 = stage1_months * trading_days_per_month
    d_ramp_end = ramp_end_months * trading_days_per_month

    # SEA sleeve: lower vol drag in sim (mirror thesis); US ops: higher idio vol / niche alpha
    base_sea = 0.00085
    base_us = 0.00055
    sea = base_sea + rng.standard_normal(n_trading_days) * 0.0105
    us_ops = base_us + rng.standard_normal(n_trading_days) * 0.0135

    w_sea = np.zeros(n_trading_days, dtype=float)
    for t in range(n_trading_days):
        if t < d1:
            w_sea[t] = 0.86
        elif t < d_ramp_end:
            w_sea[t] = 0.86 - (0.86 - 0.38) * (t - d1) / max(1, d_ramp_end - d1)
        else:
            w_sea[t] = 0.32
    w_us = 1.0 - w_sea
    r = w_sea * sea + w_us * us_ops
    equity = np.cumprod(1.0 + r)

    return PivotTimelineResult(
        equity_curve=equity,
        weight_sea=w_sea,
        daily_returns=r,
        stage1_end_day=d1,
        stage2_ramp_end_day=d_ramp_end,
        trading_days=n_trading_days,
    )


def strategic_sharpness_demo(*, seed: int = 7) -> dict[str, float]:
    """
    Stage 2 narrative bar chart: broad US indexer vs niche ops.
    Numbers are illustrative priors; replace with backtest once wired.
    """
    rng = np.random.default_rng(seed)
    jitter = rng.normal(0, 0.04, 4)
    base = np.array([0.32, 1.12, 0.98, 0.92])
    labels = [
        "S&P 500\n(generic indexing)",
        "Biotech\n(quantamental / agents)",
        "Crypto ETF\n(IBIT / ETHW harvest)",
        "Russell 2000\n(small-cap ops)",
    ]
    return {lab: float(max(0.08, b + j)) for lab, b, j in zip(labels, base, jitter)}
