from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

st.set_page_config(page_title="Crypto Alpha Arena", layout="wide")

st.title("Crypto Alpha Arena — predict returns · simulated trading")
st.caption(
    "Each agent predicts the **next-bar return** from visible history and simulates long/short; "
    "the next bar is settled with realized returns (paper only, not live)."
)

col_a, col_b = st.columns(2)
with col_a:
    steps = st.number_input("Simulation steps", min_value=50, max_value=5000, value=300, step=50)
with col_b:
    initial = st.number_input("Initial cash (USD)", min_value=1000.0, value=10_000.0, step=1000.0)

run = st.button("Run one tournament", type="primary")

session_path = ROOT / "outputs" / "last_session.json"

if run:
    from crypto_alpha_arena.arena import ArenaConfig, default_agents, run_arena
    from crypto_alpha_arena.market_feed import build_feed_from_env

    feed, mode = build_feed_from_env(["BTCUSDT", "ETHUSDT"], seed=42)
    agents = default_agents(seed=42)
    cfg = ArenaConfig(
        initial_cash_usd=float(initial),
        steps=int(steps),
        symbols=("BTCUSDT", "ETHUSDT"),
        seed=42,
    )
    with st.spinner(f"Running… ({mode})"):
        result = run_arena(agents, feed, cfg)
    st.session_state["last_result"] = {
        "meta": {**result.meta, "feed_mode": mode},
        "leaderboard": [r.model_dump() for r in result.leaderboard],
        "equity_curves": result.equity_curves,
    }

data = st.session_state.get("last_result")
if data is None and session_path.is_file():
    try:
        raw = json.loads(session_path.read_text(encoding="utf-8"))
        data = {
            "meta": raw.get("meta", {}),
            "leaderboard": raw.get("leaderboard", []),
            "equity_curves": {
                k: [(t[0], t[1]) for t in v]
                for k, v in raw.get("equity_curves", {}).items()
            },
        }
    except Exception:
        data = None

if data:
    st.subheader("Leaderboard")
    df = pd.DataFrame(data["leaderboard"])
    cols = [
        c
        for c in [
            "rank",
            "name",
            "equity_usd",
            "return_pct",
            "max_drawdown_pct",
            "direction_accuracy_pct",
            "mae_return",
        ]
        if c in df.columns
    ]
    st.dataframe(df[cols] if cols else df, use_container_width=True, hide_index=True)

    st.subheader("Equity curves")
    curves = data.get("equity_curves") or {}
    if curves:
        chart_df = pd.DataFrame(
            {name: [p[1] for p in series] for name, series in curves.items()}
        )
        st.line_chart(chart_df)

    st.caption(
        f"Initial cash: ${data['meta'].get('initial_cash_usd', 0):,.0f} · "
        f"Steps: {data['meta'].get('steps', '')} · "
        f"Feed: {data['meta'].get('feed_mode', 'n/a')} · "
        f"Mode: {data['meta'].get('mode', 'prediction_sim')}"
    )
else:
    st.info(
        'Click **Run one tournament**, or run `python scripts/run_arena.py` to generate '
        "`outputs/last_session.json` first."
    )
