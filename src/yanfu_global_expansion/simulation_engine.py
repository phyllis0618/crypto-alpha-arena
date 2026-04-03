"""Monte-style synthetic path generator for multi-market expansion studies (horizon set by caller; default ~18 months)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from yanfu_global_expansion.universe_models import GlobalMarketUniverse


@dataclass
class SimulationResult:
    daily_returns_by_sleeve: dict[str, np.ndarray]
    factor_reversal_series: dict[str, np.ndarray]
    dates_index: np.ndarray


def _sortino_ratio(returns: np.ndarray, rf: float = 0.0, periods: int = 252) -> float:
    r = np.asarray(returns, dtype=float) - rf / periods
    downside = r[r < 0]
    if len(downside) < 5:
        return float(np.mean(r) / (np.std(r) + 1e-12) * np.sqrt(periods))
    dd = np.std(downside) + 1e-12
    return float(np.mean(r) / dd * np.sqrt(periods))


def generate_paths(
    universe: GlobalMarketUniverse,
    *,
    n_days: int,
    seed: int,
) -> SimulationResult:
    """
    Synthetic paths: **not** exchange data. Latent factors + reversal noise; then a small
    sleeve-specific drift ties expected Sharpe to ``momentum_reversal_alpha_transfer`` so
    compounded equity is not dominated by vol-drag / unlucky RNG (replace with ETF returns for real use).
    """
    rng = np.random.default_rng(seed)
    n = n_days
    # Global common latent factors
    f_cn = rng.standard_normal(n) * 0.008
    f_us = rng.standard_normal(n) * 0.005
    f_em = rng.standard_normal(n) * 0.007
    f_crypto = rng.standard_normal(n) * 0.018

    out_ret: dict[str, np.ndarray] = {}
    out_fac: dict[str, np.ndarray] = {}

    for code, m in universe.markets.items():
        # Reversal factor common component scaled by transferability
        rev_core = np.zeros(n, dtype=float)
        for t in range(1, n):
            rev_core[t] = -0.12 * f_cn[t - 1] * m.momentum_reversal_alpha_transfer
        rev_noise = rng.standard_normal(n) * 0.006 * (1.6 - 0.6 * m.momentum_reversal_alpha_transfer)
        reversal = rev_core + rev_noise

        # Correlate sleeve with CN / US / EM / crypto according to priors
        w_cn = max(0.0, m.correlation_to_cn_alpha)
        w_us = 0.35 * (1.0 - w_cn) if not code.startswith("US") else 0.55
        w_em = 0.25 if code.startswith(("IN", "VN")) else 0.15
        w_cr = 0.6 if code.startswith("CRYPTO") else 0.08 * (1.0 - w_cn)

        mkt = (
            w_cn * f_cn * m.annualized_vol_hint / 0.25
            + w_us * f_us * m.annualized_vol_hint / 0.25
            + w_em * f_em * m.annualized_vol_hint / 0.25
            + w_cr * f_crypto * m.annualized_vol_hint / 0.45
        )

        vol_scaler = m.annualized_vol_hint / (np.std(mkt + reversal) * np.sqrt(252) + 1e-12)
        vol_scaler = float(np.clip(vol_scaler, 0.5, 2.5))
        strat = (mkt + reversal) * vol_scaler
        # 因子组合对 lag-CN 与项会引入**隐蔽的负漂移**（并非零均值噪声）；直接去均值再叠示意 alpha。
        strat = strat - float(np.mean(strat))
        sigma = float(np.std(strat) + 1e-12)
        # 与 alpha 迁移度挂钩的目标信息比；接入真实 ETF 收益时整段应替换为实测收益。
        target_ir = float(np.clip(0.28 + 0.92 * m.momentum_reversal_alpha_transfer, 0.22, 1.12))
        daily_alpha = target_ir * sigma / np.sqrt(252.0)
        strat = strat + daily_alpha
        out_ret[code] = strat.astype(float)
        out_fac[code] = reversal.astype(float)

    idx = np.arange(n)
    return SimulationResult(
        daily_returns_by_sleeve=out_ret,
        factor_reversal_series=out_fac,
        dates_index=idx,
    )


def factor_decay_curve(
    reversal_series: np.ndarray,
    *,
    window: int = 63,
) -> np.ndarray:
    """Rolling Sharpe of reversal sleeve; decay visible as horizon extends."""
    r = np.asarray(reversal_series, dtype=float)
    out = np.full(len(r), np.nan)
    for t in range(window, len(r)):
        seg = r[t - window : t]
        out[t] = np.mean(seg) / (np.std(seg) + 1e-12) * np.sqrt(252)
    return out


def capacity_alpha_curve(
    aum_grid_usd_bn: np.ndarray,
    *,
    base_alpha_bps: float,
    capacity_usd_bn: float,
    gamma: float = 0.55,
) -> np.ndarray:
    """Alpha erosion with AUM: alpha_net = base * (1 - (AUM/cap)^gamma) minus linear impact."""
    a = np.asarray(aum_grid_usd_bn, dtype=float)
    cap = max(capacity_usd_bn, 1e-6)
    erosion = np.clip((a / cap) ** gamma, 0.0, 0.95)
    return base_alpha_bps * (1.0 - erosion)


def crypto_risk_parity_booster(
    core_returns: np.ndarray,
    crypto_returns: np.ndarray,
    cn_trend_signal: np.ndarray,
    *,
    crypto_target_weight: float = 0.04,
    trend_lookback: int = 20,
) -> tuple[np.ndarray, float, float]:
    """
    Add crypto sleeve with target weight; gate crypto exposure with smoothed CN trend (A-share style).
    Returns (blended_returns, sortino_core, sortino_blend).
    """
    c = np.asarray(core_returns, dtype=float).ravel()
    k = np.asarray(crypto_returns, dtype=float).ravel()
    n = min(len(c), len(k))
    c, k = c[:n], k[:n]
    sig = np.asarray(cn_trend_signal, dtype=float).ravel()[:n]
    # Trend: 1 if above MA else scale down crypto
    ma = np.convolve(sig, np.ones(trend_lookback) / trend_lookback, mode="same")
    w_dyn = crypto_target_weight * (1.0 + 0.5 * np.sign(sig - ma))
    w_dyn = np.clip(w_dyn, 0.0, 0.08)
    blend = (1.0 - w_dyn) * c + w_dyn * k
    sc = _sortino_ratio(c)
    sb = _sortino_ratio(blend)
    return blend.astype(float), sc, sb


def correlation_matrix(ret_dict: dict[str, np.ndarray]) -> tuple[np.ndarray, list[str]]:
    codes = sorted(ret_dict.keys())
    mat = np.column_stack([ret_dict[c] for c in codes])
    cm = np.corrcoef(mat.T)
    return cm.astype(float), codes


def cumulative_equity(returns: np.ndarray) -> np.ndarray:
    r = np.asarray(returns, dtype=float).ravel()
    return np.cumprod(1.0 + r)


def sharpe_annualized(returns: np.ndarray, periods: int = 252) -> float:
    r = np.asarray(returns, dtype=float).ravel()
    if len(r) < 10 or np.std(r) < 1e-12:
        return 0.0
    return float(np.mean(r) / np.std(r) * np.sqrt(periods))
