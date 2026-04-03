"""Beta overlay for US/HK simulations (simple CAPM-style residualization)."""

from __future__ import annotations

from typing import Optional

import numpy as np


def apply_beta_neutral_overlay(
    strategy_returns: np.ndarray,
    market_returns: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Return hedged strategy returns and estimated beta."""
    s = np.asarray(strategy_returns, dtype=float).ravel()
    m = np.asarray(market_returns, dtype=float).ravel()
    n = min(len(s), len(m))
    s, m = s[:n], m[:n]
    if n < 30:
        return s, 0.0
    var_m = np.var(m) + 1e-12
    beta = float(np.cov(s, m)[0, 1] / var_m)
    beta = float(np.clip(beta, -2.5, 2.5))
    return (s - beta * m).astype(float), beta


def industry_style_neutralizer_placeholder(
    returns: np.ndarray,
    style_loadings: Optional[np.ndarray] = None,
) -> np.ndarray:
    if style_loadings is None:
        return np.asarray(returns, dtype=float)
    X = np.asarray(style_loadings, dtype=float)
    y = np.asarray(returns, dtype=float).ravel()
    if X.shape[0] != len(y):
        return y
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return (y - X @ beta).astype(float)
