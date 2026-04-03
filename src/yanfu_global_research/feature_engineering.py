"""Map raw AMAC-style rows + optional NAV stats into FundDNARecord."""

from __future__ import annotations

import re
from typing import Any, List, Optional

from yanfu_global_research.models import (
    AlphaStyle,
    BetaBenchmark,
    FundDNARecord,
    NavObservation,
    NavSeriesStats,
    StrategyLabel,
)
from yanfu_global_research.nav_stats import summarize_nav_returns


def _infer_beta_benchmarks(name: str) -> tuple[BetaBenchmark, list[BetaBenchmark]]:
    secondary: list[BetaBenchmark] = []
    primary = BetaBenchmark.UNKNOWN

    if "沪深300" in name:
        secondary.append(BetaBenchmark.CSI_300)
    if "中证500" in name and "中证5000" not in name:
        secondary.append(BetaBenchmark.CSI_500)
    if "中证1000" in name:
        secondary.append(BetaBenchmark.CSI_1000)
    if "中证全指" in name:
        secondary.append(BetaBenchmark.CSI_ALL_SHARE)
    if re.search(r"A500", name):
        secondary.append(BetaBenchmark.CSI_A500)
    if "小市值" in name:
        secondary.append(BetaBenchmark.SMALL_CAP_STYLE)

    # Priority for primary beta on index-enhancement names
    if re.search(r"指增|指数增强", name):
        if BetaBenchmark.CSI_A500 in secondary:
            primary = BetaBenchmark.CSI_A500
        elif BetaBenchmark.CSI_ALL_SHARE in secondary:
            primary = BetaBenchmark.CSI_ALL_SHARE
        elif BetaBenchmark.CSI_1000 in secondary:
            primary = BetaBenchmark.CSI_1000
        elif BetaBenchmark.CSI_500 in secondary:
            primary = BetaBenchmark.CSI_500
        elif BetaBenchmark.CSI_300 in secondary:
            primary = BetaBenchmark.CSI_300
        elif BetaBenchmark.SMALL_CAP_STYLE in secondary:
            primary = BetaBenchmark.SMALL_CAP_STYLE
        elif secondary:
            primary = secondary[0]
    if re.search(r"中性|对冲", name) and not re.search(r"指增|指数增强", name):
        primary = BetaBenchmark.NEUTRAL_BOOK

    return primary, list(dict.fromkeys(secondary))


def _infer_strategy_labels(name: str) -> list[StrategyLabel]:
    labels: list[StrategyLabel] = []
    if re.search(r"指增|指数增强", name):
        labels.append(StrategyLabel.INDEX_ENHANCEMENT)
    elif _looks_like_index_product_name(name):
        # 备案简称常省略「指增」但含宽基标签
        labels.append(StrategyLabel.INDEX_ENHANCEMENT)
    if re.search(r"中性|对冲", name):
        labels.append(StrategyLabel.MARKET_NEUTRAL)
        if re.search(r"指增|指数增强", name):
            pass
    if "小市值" in name:
        labels.append(StrategyLabel.SMALL_CAP_ALPHA)
    if re.search(r"CTA|期货|管理期货", name):
        labels.append(StrategyLabel.CTA)
    if re.search(r"多元|多策略|混合", name) or "鲲鹏" in name:
        labels.append(StrategyLabel.MULTI_STRATEGY)
    if not labels:
        labels.append(StrategyLabel.UNKNOWN)
    return list(dict.fromkeys(labels))


def _looks_like_index_product_name(name: str) -> bool:
    if "私募" not in name:
        return False
    return bool(
        "中证全指" in name
        or re.search(r"A500", name)
        or ("中证500" in name and "中证5000" not in name)
        or "中证1000" in name
        or "沪深300" in name
    )


def _infer_alpha_styles(
    name: str,
    labels: list[StrategyLabel],
    *,
    turnover_from_factsheet: Optional[float],
) -> List[AlphaStyle]:
    styles: list[AlphaStyle] = []

    if StrategyLabel.INDEX_ENHANCEMENT in labels:
        styles.extend([AlphaStyle.HIGH_TURNOVER, AlphaStyle.LIQUIDITY_PROVISION])
    if StrategyLabel.SMALL_CAP_ALPHA in labels:
        styles.append(AlphaStyle.SIZE_FACTOR_TILT)
    if StrategyLabel.MARKET_NEUTRAL in labels:
        styles.append(AlphaStyle.STAT_ARB)
    if "中性" in name and "指增" not in name:
        styles.append(AlphaStyle.STAT_ARB)

    # CN retail-structured markets: name-only prior (documented assumption)
    if any(
        x in name
        for x in (
            "指增",
            "指数增强",
            "小市值",
            "中证1000",
        )
    ):
        styles.append(AlphaStyle.RETAIL_SENTIMENT)

    if turnover_from_factsheet is not None and turnover_from_factsheet > 40:
        styles.append(AlphaStyle.HIGH_TURNOVER)

    out = list(dict.fromkeys(styles))
    if not out:
        out = [AlphaStyle.UNKNOWN]
    elif len(out) > 1 and AlphaStyle.UNKNOWN in out:
        out = [x for x in out if x != AlphaStyle.UNKNOWN]
    return out


def build_fund_dna(
    amac_row: dict[str, Any],
    *,
    nav_points: Optional[List[dict[str, Any]]] = None,
    turnover_annual_pct: Optional[float] = None,
) -> FundDNARecord:
    """Engineer one FundDNARecord from an AMAC fund dict."""
    fund_no = str(amac_row.get("fundNo") or amac_row.get("fund_no") or "").strip()
    name = str(amac_row.get("fundName") or amac_row.get("fund_name") or "").strip()
    if not fund_no:
        raise ValueError("AMAC row missing fundNo")

    labels = _infer_strategy_labels(name)
    primary, secondary = _infer_beta_benchmarks(name)
    alpha_styles = _infer_alpha_styles(name, labels, turnover_from_factsheet=turnover_annual_pct)

    provenance = ["amac_infodisc", "name_keyword_engineering"]

    nav_obs: list[NavObservation] = []
    if nav_points:
        for p in nav_points:
            nav_obs.append(NavObservation.model_validate(p))
        provenance.append("nav_user_supplied")

    perf = None
    if len(nav_obs) >= 2:
        perf_dict = summarize_nav_returns(nav_obs, annual_turnover_hint=turnover_annual_pct)
        perf = NavSeriesStats.model_validate(perf_dict)

    return FundDNARecord(
        fund_id=fund_no,
        fund_name=name,
        manager_name=str(amac_row.get("managerName") or "上海衍复投资管理有限公司"),
        working_state=amac_row.get("workingState"),
        custodian=amac_row.get("mandatorName"),
        strategy_labels=labels,
        primary_beta=primary,
        secondary_beta=secondary,
        alpha_styles=alpha_styles,
        nav_series=nav_obs,
        performance=perf,
        data_provenance=provenance,
    )
