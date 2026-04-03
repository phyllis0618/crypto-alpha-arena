"""Aggregate NAV-backed (realized) stats across funds for charts and JSON export."""

from __future__ import annotations

from statistics import median
from typing import Any

from yanfu_global_research.models import StrategyDatabase


def compute_realized_bundle(database: StrategyDatabase) -> dict[str, Any]:
    """
    Roll up per-fund performance (populated only when NAV series was supplied).
    Sharpe uses rf≈0; see nav_stats.summarize_nav_returns doc / methodology string below.
    """
    per_fund: list[dict[str, Any]] = []
    sharpes: list[float] = []
    turnovers: list[float] = []

    for f in database.funds:
        p = f.performance
        if p is None or p.sharpe_ratio is None:
            continue
        per_fund.append(
            {
                "fund_id": f.fund_id,
                "fund_name": f.fund_name,
                "sharpe_ratio": p.sharpe_ratio,
                "annualized_volatility": p.annualized_volatility,
                "annualized_return": p.annualized_return,
                "max_drawdown": p.max_drawdown,
                "nav_observations": len(f.nav_series),
                "annual_turnover_estimate": p.annual_turnover_estimate,
            }
        )
        sharpes.append(float(p.sharpe_ratio))
        if p.annual_turnover_estimate is not None:
            turnovers.append(float(p.annual_turnover_estimate))

    if not sharpes:
        return {
            "has_realized": False,
            "n_funds_with_sharpe": 0,
            "funds": [],
            "methodology": (
                "No NAV loaded: add --nav-csv with fund_no,as_of,nav (optional annual_turnover). "
                "Public web does not provide reliable bulk private-fund NAV."
            ),
        }

    out: dict[str, Any] = {
        "has_realized": True,
        "n_funds_with_sharpe": len(sharpes),
        "median_sharpe": float(median(sharpes)),
        "mean_sharpe": float(sum(sharpes) / len(sharpes)),
        "median_turnover": float(median(turnovers)) if turnovers else None,
        "n_funds_with_turnover": len(turnovers),
        "funds": sorted(per_fund, key=lambda x: x["fund_id"]),
        "methodology": (
            "NAV step returns; annualized vol/Sharpe via periods_per_year = n_returns / span_years; "
            "rf=0; ignores subscription fees, carry, cash drag. Not comparable to vendor 'official' Sharpe without aligning conventions."
        ),
        "data_limitation": (
            "Automated bulk real NAV is not available from AMAC. Use allocator/custodian exports or "
            "licensed data providers; do not scrape paywalled sites without permission."
        ),
    }
    return out
