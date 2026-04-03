"""Global Head of Research — gap analysis vs multi-manager standard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from yanfu_global_research.models import (
    AlphaStyle,
    BetaBenchmark,
    FundDNARecord,
    GlobalBenchmarkPack,
    StrategyDatabase,
    StrategyLabel,
)


@dataclass
class HedgeLeakageEstimate:
    fund_id: str
    score_0_1: float
    rationale: str
    drivers: list[str] = field(default_factory=list)


@dataclass
class LiquidityCapacityNote:
    summary: str
    yanfu_bucket: str
    versus_us_depth: str
    versus_apac_efficiency: str


@dataclass
class FactorContrast:
    cn_thesis: list[str]
    us_citadel_style_thesis: list[str]
    apac_jp_in_thesis: list[str]
    apac_in_thesis: list[str]


@dataclass
class AlphaDecayNarrative:
    """Structured narrative for cross-region migration of the same style."""

    headline: str
    bullets: list[str]


@dataclass
class GapAnalysisReport:
    manager: str
    fund_count: int
    strategy_mix_summary: dict[str, int]
    hedge_leakage: list[HedgeLeakageEstimate]
    liquidity_capacity: LiquidityCapacityNote
    factor_contrast: FactorContrast
    alpha_decay: AlphaDecayNarrative
    extension_hooks: dict[str, Any]


class StrategyAnalyzer:
    """
    Consumes validated StrategyDatabase (scraped DNA + optional NAV)
    and emits a gap analysis against reference regional archetypes.
    """

    def __init__(
        self,
        database: StrategyDatabase,
        global_standard: GlobalBenchmarkPack,
    ) -> None:
        self._db = database
        self._std = global_standard

    def estimate_hedge_leakage(self, fund: FundDNARecord) -> HedgeLeakageEstimate:
        """
        Heuristic \"Hedge Leakage\" proxy: structural beta / style residual when
        marketing labels say \"neutral\" but sleeves load index beta or size.
        """
        drivers: list[str] = []
        score = 0.15

        if StrategyLabel.INDEX_ENHANCEMENT in fund.strategy_labels:
            score = 0.72
            drivers.append("Explicit index-enhancement sleeve → primary benchmark beta is economic exposure.")
            if fund.primary_beta != BetaBenchmark.UNKNOWN:
                drivers.append(f"Tagged primary beta: {fund.primary_beta.value}")

        if StrategyLabel.MARKET_NEUTRAL in fund.strategy_labels:
            if StrategyLabel.INDEX_ENHANCEMENT in fund.strategy_labels:
                score = max(score, 0.55)
                drivers.append("Combined neutral + enhancement naming — basis / hedge slippage risk across books.")
            else:
                score = min(score, 0.35)
                drivers.append("Neutral-labeled sleeve — residual beta often from shorts borrow & index basis.")

        if StrategyLabel.SMALL_CAP_ALPHA in fund.strategy_labels or BetaBenchmark.SMALL_CAP_STYLE in fund.secondary_beta:
            score = min(1.0, score + 0.12)
            drivers.append("Small-cap tilt through liquidity-constrained names → style drift vs broad neutral benchmark.")

        if AlphaStyle.SIZE_FACTOR_TILT in fund.alpha_styles:
            drivers.append("Size factor emphasis (CN) does not translate 1:1 to US large-cap depth.")

        rationale = (
            "Higher score ≈ larger share of P/L explainable by beta/style vs pure factor-neutral book."
            if score >= 0.45
            else "Lower score ≈ product economics closer to cash-neutral construction (still not proof of live hedging)."
        )

        return HedgeLeakageEstimate(
            fund_id=fund.fund_id,
            score_0_1=round(score, 3),
            rationale=rationale,
            drivers=drivers,
        )

    def _strategy_mix(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self._db.funds:
            for lab in f.strategy_labels:
                k = lab.value
                counts[k] = counts.get(k, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def _liquidity_note(self) -> LiquidityCapacityNote:
        cn = next(r for r in self._std.regions if r.region_code == "CN_A_SHARE")
        us = next(r for r in self._std.regions if r.region_code == "US_MULTI_MANAGER")
        jp = next(r for r in self._std.regions if r.region_code == "APAC_JP")

        n_enh = sum(1 for f in self._db.funds if StrategyLabel.INDEX_ENHANCEMENT in f.strategy_labels)
        n_neu = sum(1 for f in self._db.funds if StrategyLabel.MARKET_NEUTRAL in f.strategy_labels)
        n_sc = sum(1 for f in self._db.funds if StrategyLabel.SMALL_CAP_ALPHA in f.strategy_labels)

        bucket = f"enhancement={n_enh}, neutral={n_neu}, smallcap_tagged={n_sc}"

        return LiquidityCapacityNote(
            summary=(
                "High-turnover CN index enhancement + small-cap sleeves consume top-of-book depth faster "
                "than the same nominal turnover in US large-cap tapes."
            ),
            yanfu_bucket=bucket,
            versus_us_depth=(
                f"US archetype assumes deeper liquidity vs CN small/mid; same notional may hit "
                f'liquidity wall earlier in CN. Reference turnover US ~{us.assumed_annual_turnover}x/yr illustrative.'
            ),
            versus_apac_efficiency=(
                f"JP archetype: {jp.liquidity_tier} — higher turnover strategies often face "
                f"lower per-name edge after costs vs CN retail-structured flow."
            ),
        )

    def _factor_contrast(self) -> FactorContrast:
        cn = next(r for r in self._std.regions if r.region_code == "CN_A_SHARE")
        us = next(r for r in self._std.regions if r.region_code == "US_MULTI_MANAGER")
        jp = next(r for r in self._std.regions if r.region_code == "APAC_JP")
        ind = next(r for r in self._std.regions if r.region_code == "APAC_IN")
        return FactorContrast(
            cn_thesis=[f"{x}: persistent in A-share microstructure" for x in cn.factor_emphasis],
            us_citadel_style_thesis=[f"{x}: competitive arms race" for x in us.factor_emphasis],
            apac_jp_in_thesis=[f"{x}" for x in jp.factor_emphasis],
            apac_in_thesis=[f"{x}" for x in ind.factor_emphasis],
        )

    def _alpha_decay(self) -> AlphaDecayNarrative:
        return AlphaDecayNarrative(
            headline="Alpha decay when migrating CN small-cap tilt → US large-cap book",
            bullets=[
                "Size and reversal sleeves scale with retail participation & mid-cap impact in CN — largely absent in US Mega-cap.",
                "Stat-arb / OB dynamics in US (Citadel-style archetype) compete on latency & data fusion; CN name-level alpha does not port without rebuild.",
                "Capacity: CN small-cap sleeves decay faster when pushing notional into names with wider spreads — US depth absorbs size but arbitrages the signal.",
                "Monitor live correlation to CSI1000 / small-cap style vs book P/L — rising beta to size factor under 'neutral' label raises effective hedge leakage.",
            ],
        )

    def gap_analysis(self) -> GapAnalysisReport:
        leakage = [self.estimate_hedge_leakage(f) for f in self._db.funds]
        return GapAnalysisReport(
            manager=self._db.manager,
            fund_count=len(self._db.funds),
            strategy_mix_summary=self._strategy_mix(),
            hedge_leakage=leakage,
            liquidity_capacity=self._liquidity_note(),
            factor_contrast=self._factor_contrast(),
            alpha_decay=self._alpha_decay(),
            extension_hooks={
                "nav_csv_path": "Inject allocator-exported NAV for fund-level Sharpe vs archetypes.",
                "fact_sheet_parser": "Optional Playwright/Selenium for authenticated doc vaults (not in OSS scope).",
                "live_risk_feed": "Book-level beta to Barra/CNE5-style factors for production hedge leakage.",
            },
        )
