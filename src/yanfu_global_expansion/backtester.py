"""Cross-market roadmap simulator: factor decay, capacity, crypto booster, neutral overlays."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from yanfu_global_expansion.risk_constraints import apply_beta_neutral_overlay
from yanfu_global_expansion.simulation_engine import (
    capacity_alpha_curve,
    correlation_matrix,
    crypto_risk_parity_booster,
    cumulative_equity,
    factor_decay_curve,
    generate_paths,
    sharpe_annualized,
)
from yanfu_global_expansion.universe_models import GlobalMarketUniverse

# ~18 calendar months of US-style sessions (252/year × 1.5); aligns with roadmap phases.
DEFAULT_SIMULATION_TRADING_DAYS = 378


@dataclass
class CrossMarketBacktestResult:
    sharpes_by_sleeve: dict[str, float]
    factor_decay_traces: dict[str, np.ndarray]
    capacity_map: dict[str, dict[str, Any]]
    correlation_matrix: np.ndarray
    correlation_labels: list[str]
    equity_cn_only: np.ndarray
    equity_global_blend: np.ndarray
    sortino_core: float
    sortino_with_crypto: float
    agentic_layer_placeholder: dict[str, Any]
    beta_neutral_meta: dict[str, float]


class CrossMarketBacktester:
    """
    High-level orchestrator. All outputs are **synthetic** unless you later
    inject vendor returns via `generate_paths` replacement.

    Default path length is `DEFAULT_SIMULATION_TRADING_DAYS` (~18 months).
    """

    def __init__(
        self,
        universe: GlobalMarketUniverse,
        *,
        n_trading_days: int = DEFAULT_SIMULATION_TRADING_DAYS,
        seed: int = 42,
    ) -> None:
        self.universe = universe
        self.n_trading_days = n_trading_days
        self.seed = seed
        self._sim: Optional[Any] = None

    async def ingest_synthetic_universe(self) -> None:
        """Async hook mirroring institutional pipelines (here: deterministic RNG)."""
        await asyncio.sleep(0)
        self._sim = generate_paths(self.universe, n_days=self.n_trading_days, seed=self.seed)

    def run_sync(self) -> CrossMarketBacktestResult:
        if self._sim is None:
            self._sim = generate_paths(self.universe, n_days=self.n_trading_days, seed=self.seed)

        sim = self._sim
        sharpes: dict[str, float] = {}
        decay_traces: dict[str, np.ndarray] = {}
        beta_meta: dict[str, float] = {}

        us_mkt = sim.daily_returns_by_sleeve["US_SP500"]
        cn_core = sim.daily_returns_by_sleeve["CN_CSI1000"]

        hedged_for_blend: dict[str, np.ndarray] = {}

        for code, r in sim.daily_returns_by_sleeve.items():
            arr = np.asarray(r, dtype=float)
            if code.startswith("US"):
                # 勿用「自身」作 US 大盘基准：对美国大盘 sleeve 与 SP 收益同一序列时 beta 剥离会把信号减没。
                if code == "US_SP500":
                    hedged_for_blend[code] = arr
                    beta_meta[code] = 1.0
                else:
                    h, b = apply_beta_neutral_overlay(arr, us_mkt[: len(arr)])
                    hedged_for_blend[code] = h
                    beta_meta[code] = b
            elif code.startswith("HK"):
                # 港股 sleeve 对恒生科技自身回归同样退化；改用 A 股核心 beta 做离岸中性示意。
                h, b = apply_beta_neutral_overlay(arr, cn_core[: len(arr)])
                hedged_for_blend[code] = h
                beta_meta[code] = b
            else:
                hedged_for_blend[code] = arr

            sharpes[code] = sharpe_annualized(hedged_for_blend[code])
            decay_traces[code] = factor_decay_curve(
                sim.factor_reversal_series[code],
                window=63,
            )

        # Capacity: illustrative grids per sleeve
        capacity: dict[str, dict[str, Any]] = {}
        aum_grid = np.logspace(-1, 1.2, 40)
        for code, m in self.universe.markets.items():
            base_bps = 110.0 * m.momentum_reversal_alpha_transfer * (30.0 / (m.impact_bps_per_million_notional + 1.0))
            cap_bn = 200.0 / (m.impact_bps_per_million_notional + 1.0)
            alphas = capacity_alpha_curve(aum_grid, base_alpha_bps=base_bps, capacity_usd_bn=cap_bn)
            capacity[code] = {
                "aum_grid_bn": aum_grid.tolist(),
                "alpha_bps_grid": alphas.tolist(),
                "implied_capacity_bn": float(cap_bn),
            }

        cm, labels = correlation_matrix(hedged_for_blend)

        # CN-only vs global blend (equal-risk sleeves ex crypto, add crypto booster)
        cn_slice = (
            hedged_for_blend["CN_CSI1000"] * 0.55
            + hedged_for_blend.get("CN_CSI500", hedged_for_blend["CN_CSI1000"]) * 0.45
        )
        global_weights = {
            "HK_HSTECH": 0.12,
            "US_SP500": 0.18,
            "US_RUT2000": 0.08,
            "IN_NIFTY50": 0.07,
            "VN_VNI": 0.05,
            "CN_CSI1000": 0.25,
            "CN_CSI500": 0.20,
        }
        g = np.zeros_like(cn_slice)
        for k, w in global_weights.items():
            g = g + w * hedged_for_blend[k]

        k_ibit = hedged_for_blend["CRYPTO_ETF_IBIT"]
        k_eth = hedged_for_blend.get("CRYPTO_ETF_ETHW", k_ibit)
        n_k = min(len(k_ibit), len(k_eth))
        crypto_combo = 0.62 * k_ibit[:n_k] + 0.38 * k_eth[:n_k]

        blended_crypto, sort_c, sort_b = crypto_risk_parity_booster(
            g[:n_k],
            crypto_combo,
            cn_slice[:n_k],
            crypto_target_weight=0.045,
        )

        eq_cn = cumulative_equity(cn_slice)
        eq_gl = cumulative_equity(blended_crypto)
        mlen = min(len(eq_cn), len(eq_gl))
        eq_cn = eq_cn[:mlen]
        eq_gl = eq_gl[:mlen]

        agentic = {
            "status": "placeholder",
            "description": "Agentic quantamental scores (e.g. US biotech trial milestones) — plug vendor NLP / structured feeds.",
            "example_signal_name": "clinical_trial_success_probability",
            "default_correlation_to_price_momo": 0.12,
        }

        return CrossMarketBacktestResult(
            sharpes_by_sleeve=sharpes,
            factor_decay_traces=decay_traces,
            capacity_map=capacity,
            correlation_matrix=cm,
            correlation_labels=labels,
            equity_cn_only=eq_cn,
            equity_global_blend=eq_gl,
            sortino_core=sort_c,
            sortino_with_crypto=sort_b,
            agentic_layer_placeholder=agentic,
            beta_neutral_meta=beta_meta,
        )
