"""NAV-derived statistics (simple institutional-grade helpers, not tax/TC-adjusted)."""

from __future__ import annotations

import math
from typing import Any, Optional

from yanfu_global_research.models import NavObservation


def summarize_nav_returns(
    series: list[NavObservation],
    *,
    annual_turnover_hint: Optional[float],
    trading_days: int = 252,
) -> dict[str, Any]:
    """trading_days kept for API compatibility; annualization uses actual n/span."""
    if len(series) < 2:
        raise ValueError("Need at least 2 NAV points")

    sorted_pts = sorted(series, key=lambda x: x.as_of)
    rets: list[float] = []
    for a, b in zip(sorted_pts, sorted_pts[1:]):
        r = b.nav / a.nav - 1.0
        rets.append(r)

    span_years = max((sorted_pts[-1].as_of - sorted_pts[0].as_of).days / 365.25, 1e-6)
    n = len(rets)
    periods_per_year = n / span_years

    mean_r = sum(rets) / n
    var = sum((r - mean_r) ** 2 for r in rets) / max(n - 1, 1)
    std = math.sqrt(var)
    ann_vol = std * math.sqrt(periods_per_year) if std > 0 else 0.0

    # Geometric annual return from total span (NAV bookends)
    ann_ret = (sorted_pts[-1].nav / sorted_pts[0].nav) ** (1 / span_years) - 1.0

    # Excess return vs rf≈0: use mean period return scaled to annual / ann vol
    sharpe = None
    if std > 1e-12 and ann_vol > 1e-12:
        sharpe = (mean_r * periods_per_year) / ann_vol

    vol = ann_vol

    # Max drawdown on NAV level
    peak = sorted_pts[0].nav
    max_dd = 0.0
    for p in sorted_pts:
        peak = max(peak, p.nav)
        dd = 1.0 - p.nav / peak
        max_dd = max(max_dd, dd)

    return {
        "observations": len(series),
        "annualized_volatility": float(vol) if math.isfinite(vol) else None,
        "annualized_return": float(ann_ret) if math.isfinite(ann_ret) else None,
        "sharpe_ratio": float(sharpe) if sharpe is not None and math.isfinite(sharpe) else None,
        "max_drawdown": float(max_dd),
        "annual_turnover_estimate": annual_turnover_hint,
    }
