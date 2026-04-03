"""Four-panel expansion pitch figure (synthetic simulation)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np

from yanfu_global_expansion.backtester import DEFAULT_SIMULATION_TRADING_DAYS, CrossMarketBacktestResult


def render_expansion_dashboard(
    result: CrossMarketBacktestResult,
    universe_codes_display: dict[str, str],
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # --- Panel 1: Sharpe transferability ---
    ax = axes[0, 0]
    labels = []
    values = []
    for code, sh in sorted(result.sharpes_by_sleeve.items(), key=lambda x: -x[1]):
        labels.append(universe_codes_display.get(code, code))
        values.append(sh)
    y_pos = np.arange(len(labels))
    ax.barh(y_pos, values, color="#2c3e50")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Simulated annualized Sharpe (post beta-neutral US/HK)")
    ax.set_title("Sleeve Sharpe — US / HK / EM / Crypto ETF vs A-share (synthetic)")
    ax.grid(True, axis="x", alpha=0.3)

    # --- Panel 2: Capacity map (log AUM vs alpha bps) ---
    ax = axes[0, 1]
    colors = plt.cm.tab10(np.linspace(0, 1, len(result.capacity_map)))
    for i, (code, pack) in enumerate(sorted(result.capacity_map.items())):
        aum = np.asarray(pack["aum_grid_bn"], dtype=float)
        alp = np.asarray(pack["alpha_bps_grid"], dtype=float)
        ax.plot(np.log10(np.clip(aum, 1e-3, None)), alp, label=universe_codes_display.get(code, code), color=colors[i])
    ax.set_xlabel("log10(AUM, USD bn) — illustrative")
    ax.set_ylabel("Expected gross alpha (bps, pre-cost sim)")
    ax.set_title("Capacity wall — alpha vs scale (model)")
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Correlation matrix ---
    ax = axes[1, 0]
    im = ax.imshow(result.correlation_matrix, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(result.correlation_labels)))
    ax.set_yticks(range(len(result.correlation_labels)))
    short = [universe_codes_display.get(c, c) for c in result.correlation_labels]
    ax.set_xticklabels(short, rotation=90, fontsize=7)
    ax.set_yticklabels(short, fontsize=7)
    ax.set_title("Cross-sleeve correlation (hedged sim returns)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # --- Panel 4: Equity curves ---
    ax = axes[1, 1]
    t = np.arange(len(result.equity_cn_only))
    ax.plot(t, result.equity_cn_only / result.equity_cn_only[0], label="CN sleeve mix (sim)", color="#c0392b", linewidth=2)
    ax.plot(
        t[: len(result.equity_global_blend)],
        result.equity_global_blend / result.equity_global_blend[0],
        label="Global multi-asset + crypto booster (sim)",
        color="#2980b9",
        linewidth=2,
    )
    ax.set_xlabel(f"Trading days (18m ≈ {DEFAULT_SIMULATION_TRADING_DAYS})")
    ax.set_ylabel("Indexed NAV")
    ax.set_title("Smoother path — global blend vs CN-only (illustrative)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Global roadmap — A-share DNA vs US / HK Tech / EM / Crypto ETF sleeves (SIMULATION)",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
