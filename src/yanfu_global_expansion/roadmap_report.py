"""18-month roadmap narrative (three phases) + executive summary markdown."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yanfu_global_expansion.backtester import DEFAULT_SIMULATION_TRADING_DAYS, CrossMarketBacktestResult


ROADMAP_PHASES: list[dict[str, Any]] = [
    {
        "phase": "Phase 1 (0–6m)",
        "title": "HK SFC Type 9 & cross-border plumbing",
        "milestones": [
            "Establish HK Type 9 footprint; trade HK + connect (Southbound/Northbound) with unified risk.",
            "Replicate CSI500/1000 enhancement DNA on HS Tech proxy with capacity discipline.",
        ],
    },
    {
        "phase": "Phase 2 (6–12m)",
        "title": "US mid-to-low frequency index enhancement at scale",
        "milestones": [
            "Deploy SPX/RUT combined book targeting >$2B with <3% tracking error budget (sim constraint).",
            "Layer quantamental / agentic research tablet for US names (biotech milestones placeholder).",
        ],
    },
    {
        "phase": "Phase 3 (12–18m)",
        "title": "Global platform — SEA + compliant crypto satellites",
        "milestones": [
            "Scale VN/IN sleeves for idiosyncratic vol harvesting (A-share analogue).",
            "Risk-parity satellite: 3–5% IBIT/ETF sleeve with CN trend gate + mean-reversion harvest.",
        ],
    },
]


def build_executive_summary(
    result: CrossMarketBacktestResult,
    *,
    target_aum_usd_bn: float = 5.0,
) -> str:
    cn_sh = result.sharpes_by_sleeve.get("CN_CSI1000", 0.0)
    us_sh = result.sharpes_by_sleeve.get("US_SP500", 0.0)
    sea_avg = (
        result.sharpes_by_sleeve.get("IN_NIFTY50", 0.0) + result.sharpes_by_sleeve.get("VN_VNI", 0.0)
    ) / 2
    cr_sh = result.sharpes_by_sleeve.get("CRYPTO_ETF_IBIT", 0.0)

    lines = [
        "# Executive Summary — Optimal Path to $5B AUM (Simulation Briefing)",
        "",
        "_Disclaimer: This document is generated from **synthetic Monte Carlo-style simulations** for "
        "internal roadmap planning. It is **not** investment advice, a forecast of Yanfu performance, or "
        "a solicitation. Replace simulations with audited historical data before board / LP use._",
        "",
        "## Headline",
        "",
        f"- **Simulation horizon:** ~{DEFAULT_SIMULATION_TRADING_DAYS} trading days (~18 months), matching the phased roadmap below.",
        f"- **Simulated sleeve Sharpe (post US/HK beta overlay):** CN CSI1000 ≈ {cn_sh:.2f}; "
        f"US SPX ≈ {us_sh:.2f}; SEA average ≈ {sea_avg:.2f}; Crypto ETF sleeve ≈ {cr_sh:.2f}.",
        f"- **Crypto booster experiment:** Sortino moves from **{result.sortino_core:.2f}** (core global blend) "
        f"to **{result.sortino_with_crypto:.2f}** with ~4.5% dynamic ETF sleeve + CN trend gate.",
        f"- **Diversification:** Cross-sleeve correlation matrix shows **modest linkage** between CN hedge basket "
        f"and US/SEA sleeves — suitable for a multi-asset platform targeting **~${target_aum_usd_bn:.1f}B** "
        "of capacity once infrastructure, licensing, and investor mandates align.",
        "",
        "## Factor & Microstructure View",
        "",
        "| Sleeve | Interpretation (sim params) |",
        "|--------|-----------------------------|",
        "| CN A-share | T+1, retail-heavy, high reversal transfer score |",
        "| HK Tech | T+0, correlated to CN flows, institutional mix |",
        "| US Large | Deep book, low impact — alpha requires **quantamental** differentiation |",
        "| SEA | High idiosyncratic vol — **alpha transfer** from A-share era analogues |",
        "| Crypto ETF | 24/7 sentiment, compliant wrapper, **Sortino booster** when trend-gated |",
        "",
        "## 18-Month Roadmap Mapping",
        "",
    ]
    for p in ROADMAP_PHASES:
        lines.append(f"### {p['phase']} — {p['title']}")
        for m in p["milestones"]:
            lines.append(f"- {m}")
        lines.append("")

    lines.extend(
        [
            "## Risk Controls (Simulation Hooks)",
            "",
            "- Beta-neutral projection vs HK/US market proxies for offshore sleeves.",
            "- Industry/style neutralizer placeholder ready for Barra-style loadings.",
            "- Capacity curves illustrate **alpha erosion** vs **AUM** — US book shows highest scale ceiling in sim.",
            "",
            "## Agentic / Fundamental Layer",
            "",
            f"- Placeholder: `{result.agentic_layer_placeholder.get('example_signal_name')}` "
            "for US biotech sleeves — integrate proprietary NLP + structured trial databases.",
            "",
            "## Recommended Next Steps",
            "",
            "1. Swap synthetic returns for ICE / Bloomberg vendor tapes per sleeve.",
            "2. Calibrate impact model to actual EMS fills + borrow costs.",
            "3. Run investor mandate constraints (UCITS, QFII, northbound limits).",
            "4. Formalize HK licensing timeline with counsel — **this doc does not constitute legal advice**.",
            "",
        ]
    )
    return "\n".join(lines)


def write_executive_summary(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
