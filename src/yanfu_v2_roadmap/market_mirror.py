"""
Stage 1 — MarketMirror: SEA vs CN vs US factor persistence (IC/IR) & settlement friction.

Synthetic validation only; swap in vendor factor returns for production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from yanfu_v2_roadmap.models import MarketTradingSpec, default_v2_universe


@dataclass
class MirrorValidationResult:
    """Outputs feeding the V2 dashboard + audit JSON."""

    factor_correlation: np.ndarray
    factor_axis_labels: list[str]
    ic_mean_by_market: dict[str, float]
    ir_by_market: dict[str, float]
    decay_ratio_sea_vs_us: float
    turnover_efficiency: dict[str, float]
    settlement_friction_bps: dict[str, float]
    meta: dict[str, Any] = field(default_factory=dict)


class MarketMirror:
    """
    Prove (in-simulation) that a **shared retail momentum / vol factor**
    persists longer (higher IC/IR, slower decay) in VN/IN vs US broad equities,
    consistent with Stage 1 "Mirror" narrative.
    """

    def __init__(
        self,
        *,
        seed: int = 42,
        markets: Optional[dict[str, MarketTradingSpec]] = None,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self.markets = markets or default_v2_universe()

    def _settlement_turnover_efficiency(self, spec: MarketTradingSpec) -> float:
        """
        T+2 / T+3 lengthens capital lock-up vs T+0/T+1.
        Map to multiplicative hit on *effective* turnover capacity (illustrative).
        """
        n = spec.settlement_days
        # T+0 baseline 1.0; each extra day beyond T+1 clips ~6% effective arb velocity
        if n <= 1:
            return 1.0
        return float(np.clip(1.0 - 0.06 * max(0, n - 1), 0.65, 1.0))

    def _stamp_friction_bps(self, spec: MarketTradingSpec) -> float:
        return float(spec.stamp_duty_bps + spec.equity_transfer_tax_bps)

    def simulate_factor_returns(self, n_days: int) -> dict[str, np.ndarray]:
        """
        Orthogonal-ish factors + loadings:
        F_cn anchor (retail HF price-vol composite proxy), F_sea loads high on F_cn,
        US_SPX orthogonal, US_RUT partial spill, Biotech idio, Crypto ETF sentiment.
        """
        rng = self.rng
        f_cn = rng.standard_normal(n_days) * 0.012
        f_sea_latent = 0.88 * f_cn + rng.standard_normal(n_days) * 0.0045
        f_us_broad = rng.standard_normal(n_days) * 0.006
        f_bio = rng.standard_normal(n_days) * 0.011
        f_crypto_et = rng.standard_normal(n_days) * 0.019

        out: dict[str, np.ndarray] = {}
        # CN — definitionally the DNA source
        out["CN_AlphaFactor"] = f_cn + rng.standard_normal(n_days) * 0.002
        # SEA mirrors CN factor structure
        out["VN_AlphaFactor"] = f_sea_latent + rng.standard_normal(n_days) * 0.003
        out["IN_AlphaFactor"] = 0.92 * f_sea_latent + rng.standard_normal(n_days) * 0.0035
        # US
        out["US_SPX_Factor"] = 0.18 * f_cn + 0.82 * f_us_broad + rng.standard_normal(n_days) * 0.002
        # Russell 2000 — "A-share style" loading on CN vol pockets
        out["US_RUT_Factor"] = 0.42 * f_cn + 0.35 * f_us_broad + rng.standard_normal(n_days) * 0.005
        # Stage 2 sleeves
        out["US_Biotech_Factor"] = 0.55 * f_bio + 0.12 * f_cn + rng.standard_normal(n_days) * 0.006
        out["ETF_Crypto_Factor"] = 0.72 * f_crypto_et + 0.08 * f_cn + rng.standard_normal(n_days) * 0.009

        return out

    def _forward_returns_from_factor(
        self,
        f: np.ndarray,
        *,
        beta_f: float = 0.095,
        noise_scale: float = 0.008,
    ) -> np.ndarray:
        """Predictable component: forward return loads on lagged factor (persistence channel)."""
        rng = self.rng
        n = len(f)
        signal = np.roll(f, 1)
        signal[0] = 0.0
        fwd = beta_f * signal + rng.standard_normal(n) * noise_scale
        return fwd.astype(float)

    def _rolling_ic(self, factor: np.ndarray, fwd: np.ndarray, window: int = 42) -> np.ndarray:
        n = len(factor)
        ics = np.full(n, np.nan)
        for t in range(window, n):
            a = factor[t - window : t]
            b = fwd[t - window : t]
            if np.std(a) < 1e-12 or np.std(b) < 1e-12:
                continue
            ics[t] = float(np.corrcoef(a, b)[0, 1])
        return ics

    def run(self, n_days: int = 378) -> MirrorValidationResult:
        specs = self.markets
        factors = self.simulate_factor_returns(n_days)

        # Align dashboard order
        axis_labels = [
            "CN\nfactor",
            "VN\nfactor",
            "IN\nfactor",
            "US_SPX\nfactor",
            "US_RUT\nfactor",
            "Biotech\nfactor",
            "Crypto\nETF factor",
        ]
        factor_matrix_keys = [
            "CN_AlphaFactor",
            "VN_AlphaFactor",
            "IN_AlphaFactor",
            "US_SPX_Factor",
            "US_RUT_Factor",
            "US_Biotech_Factor",
            "ETF_Crypto_Factor",
        ]
        mat = np.column_stack([factors[k] for k in factor_matrix_keys])
        corr = np.corrcoef(mat.T)

        ic_mean: dict[str, float] = {}
        ir: dict[str, float] = {}
        decay_early_late: dict[str, tuple[float, float]] = {}

        for label, key, beta_f, nscale in [
            ("CN CSI1000", "CN_AlphaFactor", 0.10, 0.0075),
            ("VN VNI", "VN_AlphaFactor", 0.118, 0.0070),
            ("IN Nifty", "IN_AlphaFactor", 0.115, 0.0072),
            ("US SPX", "US_SPX_Factor", 0.048, 0.0065),
            ("US Russell 2000", "US_RUT_Factor", 0.078, 0.0078),
        ]:
            f = factors[key]
            fwd = self._forward_returns_from_factor(f, beta_f=beta_f, noise_scale=nscale)
            ics = self._rolling_ic(f, fwd, window=42)
            valid = ics[np.isfinite(ics)]
            if len(valid) < 5:
                ic_mean[label] = 0.0
                ir[label] = 0.0
                continue
            m_ic = float(np.mean(valid))
            s_ic = float(np.std(valid) + 1e-12)
            ic_mean[label] = m_ic
            ir[label] = m_ic / s_ic
            half = len(valid) // 2
            early = float(np.mean(valid[:half]))
            late = float(np.mean(valid[half:]))
            decay_early_late[label] = (early, late)

        # SEA vs US decay: lower late/early ratio => less decay
        def decay_ratio(early: float, late: float) -> float:
            if abs(early) < 1e-6:
                return 1.0
            return float(late / early)

        sea_ratios = [
            decay_ratio(*decay_early_late["VN VNI"]),
            decay_ratio(*decay_early_late["IN Nifty"]),
        ]
        us_ratios = [
            decay_ratio(*decay_early_late["US SPX"]),
            decay_ratio(*decay_early_late["US Russell 2000"]),
        ]
        sea_avg = float(np.mean(sea_ratios))
        us_avg = float(np.mean(us_ratios))
        decay_ratio_sea_vs_us = float(sea_avg / (us_avg + 1e-12))

        turnover_eff = {k: self._settlement_turnover_efficiency(v) for k, v in specs.items()}
        friction_bps = {k: self._stamp_friction_bps(v) for k, v in specs.items()}

        return MirrorValidationResult(
            factor_correlation=corr,
            factor_axis_labels=axis_labels,
            ic_mean_by_market=ic_mean,
            ir_by_market=ir,
            decay_ratio_sea_vs_us=decay_ratio_sea_vs_us,
            turnover_efficiency=turnover_eff,
            settlement_friction_bps=friction_bps,
            meta={
                "stage1_hypothesis": "SEA IC decay slower than US (ratio>1 favours mirror)",
                "decay_early_late": {k: list(v) for k, v in decay_early_late.items()},
            },
        )
