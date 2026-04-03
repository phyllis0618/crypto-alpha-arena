"""V2 roadmap figure: Alpha similarity heatmap + Strategic Sharpness + 18m pivot P&L."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import gridspec

from yanfu_v2_roadmap.market_mirror import MirrorValidationResult
from yanfu_v2_roadmap.roadmap_sim import PivotTimelineResult, strategic_sharpness_demo


def render_v2_roadmap_dashboard(
    mirror: MirrorValidationResult,
    pivot: PivotTimelineResult,
    output_path: Path,
    *,
    sharpness: dict[str, float] | None = None,
) -> None:
    sharp = sharpness or strategic_sharpness_demo()

    fig = plt.figure(figsize=(15, 11))
    gs = gridspec.GridSpec(3, 2, height_ratios=[1.15, 0.95, 1.0], width_ratios=[1.12, 1.0], hspace=0.38, wspace=0.28)

    # --- Panel A: factor correlation heatmap (mirror) ---
    ax_h = fig.add_subplot(gs[0, 0])
    im = ax_h.imshow(mirror.factor_correlation, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax_h.set_xticks(range(len(mirror.factor_axis_labels)))
    ax_h.set_yticks(range(len(mirror.factor_axis_labels)))
    ax_h.set_xticklabels(mirror.factor_axis_labels, fontsize=8, rotation=0)
    ax_h.set_yticklabels(mirror.factor_axis_labels, fontsize=8)
    ax_h.set_title("Alpha Similarity — Factor Return Correlation\n(CN ↔ SEA mirror vs US sleeves)", fontsize=11, fontweight="bold")
    for i in range(mirror.factor_correlation.shape[0]):
        for j in range(mirror.factor_correlation.shape[1]):
            ax_h.text(j, i, f"{mirror.factor_correlation[i, j]:.2f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(im, ax=ax_h, fraction=0.046, pad=0.04)

    # --- Panel B: IC / IR summary table text ---
    ax_txt = fig.add_subplot(gs[0, 1])
    ax_txt.axis("off")
    lines = [
        "Stage 1 — Factor persistence (synthetic IC/IR)",
        "",
        f"SEA vs US decay ratio (late/early IC): {mirror.decay_ratio_sea_vs_us:.2f}",
        "  (>1 ⇒ SEA IC fades slower vs US in this calibration)",
        "",
    ]
    for k, v in mirror.ic_mean_by_market.items():
        ir = mirror.ir_by_market.get(k, 0.0)
        lines.append(f"  {k}: mean IC {v:+.3f}, IR {ir:.2f}")
    lines.extend(
        [
            "",
            "Settlement drag (turnover efficiency, T+n):",
        ]
    )
    for code in ("VN_VNI", "IN_NIFTY", "US_SP500", "CN_CSI1000"):
        if code in mirror.turnover_efficiency:
            eff = mirror.turnover_efficiency[code]
            fr = mirror.settlement_friction_bps.get(code, 0.0)
            lines.append(f"  {code}: eff×{eff:.2f}, fees ~{fr:.0f} bps")
    ax_txt.text(0.02, 0.98, "\n".join(lines), transform=ax_txt.transAxes, va="top", fontsize=8.5, family="monospace")

    # --- Panel C: Strategic Sharpness ---
    ax_b = fig.add_subplot(gs[1, :])
    labels = list(sharp.keys())
    vals = [sharp[k] for k in labels]
    colors = ["#95a5a6", "#e74c3c", "#3498db", "#9b59b6"]
    x = np.arange(len(labels))
    ax_b.bar(x, vals, color=colors, edgecolor="white", linewidth=0.8)
    ax_b.axhline(0.5, color="#7f8c8d", linestyle="--", linewidth=1, alpha=0.7)
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(labels, fontsize=9)
    ax_b.set_ylabel("Illustrative Sharpe (Stage 2 priors)")
    ax_b.set_title('Strategic Sharpness — Broad S&P Indexing vs US "Special Ops" Entry Points', fontsize=11, fontweight="bold")
    ax_b.grid(True, axis="y", alpha=0.3)

    # --- Panel D: 18m pivot P&L ---
    ax_p = fig.add_subplot(gs[2, :])
    t = np.arange(len(pivot.equity_curve))
    eq = pivot.equity_curve / pivot.equity_curve[0]
    ax_p.plot(t, eq, color="#2c3e50", linewidth=2, label="Blended roadmap NAV (sim)")
    ax_p.axvline(pivot.stage1_end_day, color="#27ae60", linestyle="--", linewidth=1.2, label="~6m: end Stage 1 (SEA-heavy)")
    ax_p.axvline(pivot.stage2_ramp_end_day, color="#e67e22", linestyle="--", linewidth=1.2, label="~12m: ramp completes (US ops ↑)")
    s1 = min(pivot.stage1_end_day, len(t))
    s2 = min(pivot.stage2_ramp_end_day, len(t))
    ax_p.axvspan(0, s1, alpha=0.12, color="green", label="Stage 1: SEA-heavy")
    if s2 < len(t):
        ax_p.axvspan(s2, len(t), alpha=0.10, color="#f39c12", label="12–18m: US ops plateau")
    ax_p.set_xlabel("Trading days (~18m ≈ 378)")
    ax_p.set_ylabel("Indexed cumulative P&L (synthetic)")
    ax_p.set_title("Pivot Timeline — SEA Funding the US Alpha Lab (illustrative capital glide)", fontsize=11, fontweight="bold")
    ax_p.legend(loc="upper left", fontsize=8, ncol=2)
    ax_p.grid(True, alpha=0.3)

    fig.suptitle(
        "Global Quant Validation — Stage 1 SEA Mirror + Stage 2 US Special Ops (SIMULATION / NOT LIVE PERFORMANCE)",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.93, bottom=0.06, hspace=0.45, wspace=0.35)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
