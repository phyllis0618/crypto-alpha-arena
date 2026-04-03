"""
BTC Arena — single model, CoinGlass data, paper simulation.

Run: cd crypto-alpha-arena && PYTHONPATH=src python -m streamlit run frontend/btc_dashboard.py
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from btc_arena.models import SimState, UnifiedMarketSnapshot
from btc_arena.pipeline import run_pipeline_tick
from btc_arena.rumor_chat import extract_rumors_ollama

st.set_page_config(page_title="BTC Arena", layout="wide")

st.title("BTC Arena — single model · CoinGlass · paper trading")
st.caption(
    "Data → UnifiedMarketSnapshot · predict agents → paper sim · Rumor lab: extract → validation (sidebar)"
)

with st.expander("Data flow & agent flow", expanded=True):
    st.markdown("**DATA FLOW** — feeds merged into one snapshot each tick")
    st.code(
        """
CoinGlass API (OHLC, funding, OI, F&G) ──┐
                                         ├──► UnifiedMarketSnapshot
FRED DFF + SEC RSS (macro text, DFF Δ) ──┤      · market, coinglass, analytics (RSI, vol…)
                                         │      · macro (MacroRegimeSignal)
X API v2 optional (Bearer, timelines) ───┘      · social (tweets)
Optional REST probes → coinglass_endpoints[] (diagnostics; not merged into price path)
""",
        language="text",
    )
    st.markdown("**AGENT FLOW** — who reads what, and what they output")
    st.code(
        """
┌─ MacroNewsAgent (data→regime, not a trade)
│   IN:  F&G, Fed DFF context, SEC headlines (from snapshot / fetch)
│   OUT: macro regime fields → optional rules edge nudge (BTC_ARENA_USE_MACRO)
│
├─ Predict agent (exactly one per tick)
│   Rules  IN: returns, funding, F&G, macro regime, optional nudge
│        OUT: UP | DOWN | FLAT
│   Ollama IN: full snapshot JSON (if BTC_ARENA_USE_LLM=1)
│        OUT: UP | DOWN | FLAT
│        └──────────────► Paper simulator → equity / PnL
│
└─ Rumor branch (sidebar, advisory only — does not move the trade)
    Rumor extract agent (Ollama)
        IN:  user paste + market summary string (price, RSI, funding, macro one-liner)
        OUT: JSON { rumors[], … }
            │
            ▼
    Rumor validation agent (Ollama)     ← turns claims into rumor_signal
        IN:  extraction JSON + same user text + same context
        OUT: JSON { rumor_signal, strength, verdicts… }   (BTC_ARENA_RUMOR_VALIDATE=0 skips)
""",
        language="text",
    )


def _mask_api_key(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return "(empty)"
    if len(s) <= 8:
        return s[:2] + "…" + s[-2:]
    return s[:4] + "…" + s[-4:]


def _render_data_diagnostics(snap: UnifiedMarketSnapshot) -> None:
    """Surface CoinGlass / env issues so misconfiguration is obvious."""
    key_raw = os.getenv("COINGLASS_API_KEY", "")
    key_ok = bool(key_raw.strip())
    base = os.getenv("COINGLASS_API_BASE", "https://open-api-v4.coinglass.com")
    ex = os.getenv("COINGLASS_FUTURES_EXCHANGE", "Binance")
    sym = os.getenv("COINGLASS_FUTURES_SYMBOL", "BTCUSDT")
    interval = os.getenv("COINGLASS_FUTURES_INTERVAL", "4h")

    lines: list[str] = []
    if not key_ok:
        lines.append(
            "**Missing API key:** set `COINGLASS_API_KEY` in `.env` at the project root. "
            "Get a key from [coinglass.com](https://www.coinglass.com) → account → API. "
            "Requests use header `CG-API-KEY`."
        )

    err_parts: list[str] = []
    if snap.market.error:
        err_parts.append(f"Market: `{snap.market.error}`")
    if snap.coinglass.error:
        err_parts.append(f"CoinGlass context: `{snap.coinglass.error}`")
    if err_parts:
        lines.append("**Errors returned:** " + " · ".join(err_parts))

    n_candles = len(snap.candles)
    if key_ok and n_candles == 0:
        lines.append(
            "**No OHLC candles:** check (1) key is valid and not expired, (2) your plan allows the "
            f"requested interval (`COINGLASS_FUTURES_INTERVAL` is `{interval}`; ensure your plan allows it), "
            f"(3) `COINGLASS_FUTURES_EXCHANGE`/`COINGLASS_FUTURES_SYMBOL` match a pair CoinGlass supports "
            f"(currently `{ex}` / `{sym}`)."
        )
    if key_ok and snap.market.last_price <= 0 and not err_parts:
        lines.append(
            "**Last price is zero:** `coins-markets` may not have returned a BTC row, or the response "
            "shape changed. See raw excerpt in server logs / CoinGlass docs."
        )

    combined_err = " ".join(str(x) for x in [snap.market.error, snap.coinglass.error] if x)
    if "429" in combined_err or "Too Many" in combined_err or "rate limit" in combined_err.lower():
        lines.append(
            "**HTTP 429 / Too Many Requests:** CoinGlass is throttling your key. Set **`COINGLASS_PROBE_MAX=0`** "
            "in `.env` (disables extra endpoint probes), wait 1–2 minutes, then refresh. OHLC requests retry "
            "with backoff automatically."
        )

    n_ok = sum(1 for x in snap.coinglass_endpoints if x.ok)
    n_ep = len(snap.coinglass_endpoints)

    with st.expander("Data diagnostics & CoinGlass API", expanded=bool(lines) or not key_ok):
        llm_on = os.getenv("BTC_ARENA_USE_LLM", "").strip().lower() in ("1", "true", "yes")
        ollama_url = os.getenv("BTC_ARENA_OLLAMA_URL", "http://127.0.0.1:11434")
        ollama_model = os.getenv("BTC_ARENA_OLLAMA_MODEL", "llama3.2")
        st.markdown(
            f"- **COINGLASS_API_KEY:** `{_mask_api_key(key_raw)}` ({'set' if key_ok else 'NOT SET'})\n"
            f"- **COINGLASS_API_BASE:** `{base}`\n"
            f"- **Futures OHLC:** exchange=`{ex}`, symbol=`{sym}`, interval=`{interval}` (snapshot: `{snap.bar_interval}`)\n"
            f"- **Candles loaded:** {n_candles}\n"
            f"- **Last price:** {snap.market.last_price:,.2f}\n"
            f"- **CoinGlass derivatives OK:** {'yes' if snap.coinglass.ok else 'no'}\n"
            f"- **REST probes OK:** {n_ok}/{n_ep}\n"
            f"- **BTC_ARENA_USE_LLM:** {'on (Ollama)' if llm_on else 'off (rules)'}\n"
            f"- **Ollama:** `{ollama_url}` · model=`{ollama_model}`"
        )
        if lines:
            st.error("\n\n".join(lines))
        elif key_ok and n_candles > 0 and snap.market.last_price > 0:
            st.success("CoinGlass pipeline returned price and candles; configuration looks usable.")
        elif key_ok:
            st.warning(
                "Key is set but data is incomplete — review the messages above and CoinGlass dashboard "
                "for quota / plan limits."
            )


st.sidebar.header("Refresh")
refresh_sec = st.sidebar.slider("Auto-refresh interval (seconds)", 5, 120, 15)
use_auto = st.sidebar.checkbox("Enable auto-refresh", value=False)

if "sim" not in st.session_state:
    st.session_state.sim = SimState()
if "prev_price" not in st.session_state:
    st.session_state.prev_price = None
if "pending" not in st.session_state:
    st.session_state.pending = None
if "rumor_messages" not in st.session_state:
    st.session_state.rumor_messages = []


def render_dashboard() -> None:
    snap, pred, sim = run_pipeline_tick(
        st.session_state.sim,
        st.session_state.prev_price,
        st.session_state.pending,
    )
    st.session_state.last_snap = snap
    st.session_state.sim = sim
    st.session_state.pending = pred
    st.session_state.prev_price = snap.market.last_price

    _render_data_diagnostics(snap)

    b = snap.market
    cg = snap.coinglass
    a = snap.analytics

    if b.error:
        st.warning(f"Market feed: {b.error} (source={b.source})")

    tab_ov, tab_alt, tab_an, tab_api = st.tabs(
        ["Overview", "Macro & X", "Analytics & volume", "CoinGlass REST probes"]
    )

    with tab_ov:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BTC last (USDT)", f"{b.last_price:,.2f}")
        c2.metric("24h change %", f"{b.price_change_pct_24h:+.2f}%")
        c3.metric("24h quote volume (USDT)", f"{b.quote_volume_usd_24h:,.0f}")
        c4.metric("Paper equity (USD)", f"{st.session_state.sim.equity_usd:,.2f}")

        st.subheader("Single-model prediction")
        p1, p2, p3 = st.columns(3)
        p1.metric("Direction", pred.direction)
        p2.metric("Confidence", f"{pred.confidence:.2f}")
        p3.metric("Model", pred.model)
        st.info(pred.reasoning)

        st.subheader("BTC close (CoinGlass futures OHLC)")
        df = pd.DataFrame([{"t": c.ts, "close": c.close} for c in snap.candles[-120:]])
        if not df.empty:
            st.line_chart(df.set_index("t"))
        else:
            st.caption("No candle rows to chart — see **Data diagnostics** above.")

        st.subheader("CoinGlass (derivatives snapshot)")
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Funding", f"{cg.funding_rate_avg:.6f}" if cg.funding_rate_avg is not None else "—")
        g2.metric("OI USD", f"{cg.open_interest_usd:,.0f}" if cg.open_interest_usd else "—")
        g3.metric("F&G", f"{cg.fear_greed}" if cg.fear_greed is not None else "—")
        g4.metric("Fetch OK", "yes" if cg.ok else "no")
        if cg.error:
            st.caption(f"CoinGlass: {cg.error}")

        st.subheader("Paper equity (recent)")
        if st.session_state.sim.history:
            eq_df = pd.DataFrame(
                [{"t": x.ts, "equity": x.equity_after} for x in st.session_state.sim.history[-200:]]
            )
            if not eq_df.empty:
                st.line_chart(eq_df.set_index("t"))
            st.dataframe(
                pd.DataFrame([x.model_dump() for x in st.session_state.sim.history[-25:]]),
                use_container_width=True,
            )
        else:
            st.caption("Settlement rows appear after a few refreshes.")

    with tab_alt:
        mx = snap.macro
        st.subheader("FRED + SEC (Macro/News agent)")
        st.caption(
            "Same stack as **Alpha Arena** `MacroNewsAgent`: **DFF** = Fed effective funds rate (daily); "
            "**SEC** press-release RSS filtered for crypto keywords + enforcement tone. "
            "Blended with CoinGlass **Fear & Greed** into `risk_on` / `risk_off` / `neutral` — see "
            "`macro_agent.py` `_score_to_regime`. **Requires** `FRED_API_KEY` in `.env` for Fed series."
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Macro regime", str(mx.regime))
        c2.metric("Regime confidence", f"{mx.confidence:.2f}")
        c3.metric("Fed DFF %", f"{mx.fed_effective_rate_pct:.4f}" if mx.fed_effective_rate_pct else "—")
        st.markdown(f"**Fed note:** {mx.fed_note or '—'}")
        st.markdown(f"**Reasoning:** {mx.reasoning or '—'}")
        if mx.sec_crypto_headline_sample:
            st.text_area("SEC crypto-related headlines (sample)", mx.sec_crypto_headline_sample[:2000], height=120)
        sx = snap.social
        st.subheader("X (Twitter API v2)")
        st.caption(
            "Official API only — set `TWITTER_BEARER_TOKEN` + `TWITTER_MONITOR_USERNAMES=elonmusk,realDonaldTrump`. "
            "Requires [Twitter Developer](https://developer.twitter.com/) access (rate limits apply). "
            "No Musk/Trump scraping without API; Truth Social / other networks are not integrated."
        )
        if sx.ok and sx.tweets:
            st.dataframe(
                pd.DataFrame([t.model_dump() for t in sx.tweets]),
                use_container_width=True,
                height=min(400, 80 + len(sx.tweets) * 36),
            )
        else:
            st.info(sx.note or sx.error or "No tweets loaded.")

    with tab_an:
        st.markdown(
            f"**Bar interval:** `{snap.bar_interval}` · **Bars:** {a.n_bars} · "
            f"**Vol USD (last bar):** {a.volume_usd_last:,.0f}"
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("RSI(14)", f"{a.rsi_14:.1f}" if a.rsi_14 is not None else "—")
        m2.metric("Vol / SMA20", f"{a.volume_ratio_vs_sma:.2f}" if a.volume_ratio_vs_sma is not None else "—")
        m3.metric("Realized vol (short)", f"{a.realized_vol_short:.4f}" if a.realized_vol_short is not None else "—")
        m4.metric(
            "HL range (last bar)",
            f"{a.high_low_range_pct_last:.4f}" if a.high_low_range_pct_last is not None else "—",
        )

        vdf = pd.DataFrame(
            [
                {"t": c.ts, "volume_usd": c.volume_usd, "close": c.close}
                for c in snap.candles[-120:]
            ]
        )
        if not vdf.empty:
            st.subheader("Volume (USD) per bar")
            st.line_chart(vdf.set_index("t")[["volume_usd"]])
            st.subheader("Close (same window)")
            st.line_chart(vdf.set_index("t")[["close"]])
        else:
            st.caption("No candles for analytics.")

    with tab_api:
        st.caption(
            "Parallel GETs to documented CoinGlass paths (some may fail depending on plan or params). "
            "Adjust `COINGLASS_PROBE_MAX` in `.env` to change how many run."
        )
        rows = [x.model_dump() for x in snap.coinglass_endpoints]
        if rows:
            edf = pd.DataFrame(rows)
            st.dataframe(
                edf[["name", "ok", "http_status", "data_rows", "path", "error", "preview"]],
                use_container_width=True,
                height=420,
            )
        else:
            st.info("No probe rows (missing API key or fetch error).")

    st.caption(f"Snapshot UTC: {snap.fetched_at.isoformat()}")


if use_auto and hasattr(st, "fragment"):

    @st.fragment(run_every=timedelta(seconds=refresh_sec))
    def _auto_dash() -> None:
        render_dashboard()

    _auto_dash()
else:
    render_dashboard()
    if st.sidebar.button("Refresh now"):
        st.rerun()

with st.sidebar:
    st.divider()
    st.subheader("Rumor lab")
    st.caption(
        "Paste social/news text. Ollama: extract agent → validation agent (rumor_signal); "
        "heuristic fallback if offline. Set BTC_ARENA_RUMOR_VALIDATE=0 to skip validation."
    )
    for msg in st.session_state.rumor_messages[-16:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("Analyze text for rumors…"):
        snap_for_chat = st.session_state.get("last_snap")
        with st.spinner("Analyzing…"):
            reply = extract_rumors_ollama(prompt, snap_for_chat)
        st.session_state.rumor_messages.append({"role": "user", "content": prompt})
        st.session_state.rumor_messages.append(
            {"role": "assistant", "content": f"```json\n{reply}\n```"}
        )
        st.rerun()
