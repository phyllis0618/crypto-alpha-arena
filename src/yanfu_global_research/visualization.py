"""Multi-panel benchmark chart: regional archetypes vs Yanfu name-DNA prior (English labels in PNG for font portability)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
from matplotlib import gridspec
import numpy as np

from yanfu_global_research.models import GlobalBenchmarkPack, StrategyDatabase, StrategyLabel

# English in figure — full 中文解读见 Streamlit 页面
REGION_LABEL = {
    "CN_A_SHARE": "CN A-share\n(retail-structured)",
    "US_MULTI_MANAGER": "US multi-strat\n(Citadel-style archetype)",
    "APAC_JP": "Japan",
    "APAC_IN": "India",
}

FACTOR_PRETTY = {
    "size_tilt_small": "Small-cap tilt",
    "short_term_reversal": "Short-term reversal",
    "retail_flow_proxies": "Retail-flow proxy",
    "order_book_microstructure": "Order-book microstructure",
    "alternative_data": "Alternative data",
    "cross_sectional_stat_arb": "X-section stat-arb",
    "low_vol_carry": "Low-vol / carry",
    "quality_momentum_blend": "Quality + momentum",
    "momentum_quality": "Momentum + quality",
    "midcap_liquidity_skew": "Mid-cap liquidity skew",
}


def _yanfu_prior_point(database: StrategyDatabase, regions: list) -> tuple[float, float, float, float]:
    n_enh = max(
        1,
        sum(1 for f in database.funds if StrategyLabel.INDEX_ENHANCEMENT in f.strategy_labels),
    )
    n_neu = sum(1 for f in database.funds if StrategyLabel.MARKET_NEUTRAL in f.strategy_labels)
    n_tot = max(len(database.funds), 1)
    w_enh = n_enh / n_tot
    w_neu = n_neu / n_tot
    cn_ref = next(r for r in regions if r.region_code == "CN_A_SHARE")
    yanfu_turnover = cn_ref.assumed_annual_turnover * (0.75 + 0.35 * w_enh)
    yanfu_sharpe = cn_ref.assumed_sharpe_net * (0.92 - 0.08 * w_neu) + 0.03
    return yanfu_turnover, yanfu_sharpe, w_enh, w_neu


def plot_comparison_dashboard(
    database: StrategyDatabase,
    benchmarks: GlobalBenchmarkPack,
    output_path: Path,
    *,
    realized: Optional[dict[str, Any]] = None,
) -> None:
    """
    Four panels:
    (1) Scatter: illustrative turnover vs illustrative Sharpe — relative trading intensity vs assumed risk-adjusted return prior.
    (2) Bar: turnover by region.
    (3) Bar: illustrative Sharpe by region.
    (4) Text: factor emphasis + liquidity/capacity tags from reference JSON.
    """
    regions = benchmarks.regions
    codes = [r.region_code for r in regions]
    labels = [REGION_LABEL.get(c, c) for c in codes]
    turnovers = [r.assumed_annual_turnover for r in regions]
    sharpes = [r.assumed_sharpe_net for r in regions]

    y_turn, y_sharpe, w_enh, w_neu = _yanfu_prior_point(database, regions)

    real_x: Optional[float] = None
    real_y: Optional[float] = None
    real_n = 0
    if realized and realized.get("has_realized"):
        real_n = int(realized.get("n_funds_with_sharpe") or 0)
        real_y = float(realized["median_sharpe"])
        mt = realized.get("median_turnover")
        if mt is not None:
            real_x = float(mt)
        else:
            real_x = y_turn

    fig = plt.figure(figsize=(14, 11))
    gs = gridspec.GridSpec(2, 2, height_ratios=[1.15, 1.0], hspace=0.40, wspace=0.28)

    ax0 = fig.add_subplot(gs[0, 0])
    ax0.scatter(turnovers, sharpes, s=140, c="#34495e", zorder=3, label="Regional archetypes (assumed)")
    for x, y, c in zip(turnovers, sharpes, codes):
        ax0.annotate(REGION_LABEL.get(c, c).replace("\n", " "), (x, y), xytext=(5, 3), textcoords="offset points", fontsize=8)
    ax0.scatter(
        [y_turn],
        [y_sharpe],
        s=280,
        c="#e74c3c",
        marker="*",
        zorder=5,
        label="Yanfu DNA prior (not realized)",
        edgecolors="white",
        linewidths=1,
    )
    if real_x is not None and real_y is not None:
        ax0.scatter(
            [real_x],
            [real_y],
            s=200,
            c="#27ae60",
            marker="D",
            zorder=6,
            label=f"Yanfu NAV-backed median (n={real_n})",
            edgecolors="white",
            linewidths=1,
        )
    ax0.set_xlabel("Assumed annual turnover (×/yr)\n↑ higher → more trading, impact/capacity sensitive")
    ax0.set_ylabel("Sharpe (illustrative priors vs NAV-backed median if green)")
    ax0.set_title("(1) Turnover × Sharpe\n* prior = name-mix tilt; ◆ = median from loaded NAV (rf=0)")
    ax0.grid(True, alpha=0.35)
    ax0.legend(loc="lower right", fontsize=8)

    ax1 = fig.add_subplot(gs[0, 1])
    xpos = np.arange(len(labels))
    colors = ["#3498db", "#9b59b6", "#1abc9c", "#f39c12"]
    ax1.bar(xpos, turnovers, color=colors, edgecolor="white", linewidth=0.8)
    ax1.axhline(y_turn, color="#e74c3c", linestyle="--", linewidth=2, label=f"Yanfu prior ({y_turn:.1f}×)")
    if real_x is not None and realized and realized.get("median_turnover") is not None:
        ax1.axhline(real_x, color="#27ae60", linestyle="--", linewidth=2, label=f"NAV median turnover ({real_x:.1f}×)")
    ax1.set_xticks(xpos)
    ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylabel("Turnover (×/yr)")
    ax1.set_title("(2) Who runs higher turnover?")
    ax1.legend(loc="upper right", fontsize=8)
    ax1.grid(True, axis="y", alpha=0.3)

    ax2 = fig.add_subplot(gs[1, 0])
    ax2.bar(xpos, sharpes, color=colors, edgecolor="white", linewidth=0.8)
    ax2.axhline(y_sharpe, color="#e74c3c", linestyle="--", linewidth=2, label=f"Yanfu prior ({y_sharpe:.2f})")
    if real_y is not None:
        ax2.axhline(real_y, color="#27ae60", linestyle="--", linewidth=2, label=f"NAV median Sharpe ({real_y:.2f})")
    ax2.set_xticks(xpos)
    ax2.set_xticklabels(labels, fontsize=8)
    ax2.set_ylabel("Illustrative Sharpe")
    ax2.set_title("(3) Sharpe: regional priors vs NAV median (green line if CSV loaded)")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, axis="y", alpha=0.3)

    ax3 = fig.add_subplot(gs[1, 1])
    ax3.axis("off")
    lines = [
        "(4) What each archetype emphasizes (from reference JSON, not firm disclosure)",
        "",
        f"Yanfu snapshot: index-enh ~{w_enh:.0%} of funds, neutral-tagged ~{w_neu:.0%} (by count).",
        "",
    ]
    if realized and realized.get("has_realized"):
        mt = realized.get("median_turnover")
        mt_s = "n/a" if mt is None else f"{float(mt):.1f}x"
        lines.append(
            f"NAV-backed: median Sharpe={realized['median_sharpe']:.3f} over "
            f"{realized['n_funds_with_sharpe']} fund(s); turnover median={mt_s}."
        )
        lines.append(str(realized.get("methodology", "")))
        lines.append("")
    elif realized:
        lines.append("NAV-backed: (no NAV CSV loaded — green marker/lines omitted)")
        lines.append("")
    for r in regions:
        lab = REGION_LABEL.get(r.region_code, r.region_code).replace("\n", " ")
        fac = "; ".join(FACTOR_PRETTY.get(f, f) for f in r.factor_emphasis)
        lines.append(f"[{lab}]")
        lines.append(f"  Factors: {fac}")
        lines.append(f"  Liquidity: {r.liquidity_tier}")
        lines.append(f"  vs US large-cap capacity: {r.capacity_headroom_vs_us_large_cap}")
        lines.append("")
    ax3.text(0.02, 0.98, "\n".join(lines), transform=ax3.transAxes, fontsize=8.5, verticalalignment="top", family="monospace")

    fig.suptitle(
        "Yanfu vs global regional quant archetypes — structural comparison (illustrative; not investment advice)",
        fontsize=12,
        fontweight="bold",
        y=0.98,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_sharpe_vs_turnover(
    database: StrategyDatabase,
    benchmarks: GlobalBenchmarkPack,
    output_path: Path,
    *,
    title: str = "Illustrative Sharpe vs Turnover — Regions vs Yanfu mix",
) -> None:
    plot_comparison_dashboard(database, benchmarks, output_path)
