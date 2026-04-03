from __future__ import annotations

import asyncio
import html
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from alpha_arena.live_feed import interval_from_env, live_feed_loop, load_env
from alpha_arena.persistence import load_leaderboard_snapshot, load_live_context_snapshot
from alpha_arena.state import get_live_feed_state, get_tournament_director

logger = logging.getLogger("alpha_arena.api")

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _merged_live_context() -> dict[str, Any]:
    s = get_live_feed_state()
    if s.context:
        return s.context
    return load_live_context_snapshot()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(_REPO_ROOT / ".env")
    load_env()
    enabled = os.getenv("ENABLE_LIVE_FEED", "1").strip().lower() not in ("0", "false", "no")
    task: Optional[asyncio.Task] = None
    if enabled:
        interval = interval_from_env()
        logger.info("Starting live feed: interval=%ss (set ENABLE_LIVE_FEED=0 to disable)", interval)
        task = asyncio.create_task(live_feed_loop(interval))
    else:
        logger.info("Live feed disabled (ENABLE_LIVE_FEED=0)")
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Alpha Arena", version="0.2.1", lifespan=lifespan)


def _leaderboard_entries():
    d = get_tournament_director()
    if d is not None:
        return d.last_leaderboard
    return load_leaderboard_snapshot()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/live/status")
def api_live_status() -> dict[str, Any]:
    s = get_live_feed_state()
    return {
        "enabled": os.getenv("ENABLE_LIVE_FEED", "1") not in ("0", "false"),
        "poll_interval_sec": s.poll_interval_sec,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "tick": s.tick,
        "last_error": s.last_error,
        "has_cached_context": bool(s.context),
    }


@app.get("/api/context")
def api_context() -> dict[str, Any]:
    ctx = _merged_live_context()
    st = get_live_feed_state()
    if not ctx:
        return {"macro": {}, "coinglass": {}, "agents": [], "message": "Waiting for first live poll…"}
    out = dict(ctx)
    out["meta"] = {**(ctx.get("meta") or {}), "updated_at": st.updated_at.isoformat() if st.updated_at else None}
    return out


@app.get("/api/leaderboard")
def api_leaderboard() -> dict[str, Any]:
    entries = _leaderboard_entries()
    ctx = _merged_live_context()
    if not entries:
        return {
            "leaderboard": [],
            "message": "No leaderboard yet — optional: PYTHONPATH=src python scripts/run_alpha_backtest.py",
            "live_context": ctx,
        }
    out = []
    for i, e in enumerate(entries):
        out.append(
            {
                "rank": i + 1,
                "agent_id": e.agent_id,
                "name": e.name,
                "equity_usd": e.equity_usd,
                "total_return_pct": e.total_return,
                "sharpe_ratio": e.sharpe_ratio,
                "sortino_ratio": e.sortino_ratio,
                "max_drawdown_pct": e.max_drawdown_pct,
                "diversity_factor": e.diversity_factor,
                "score": e.score,
            }
        )
    return {"leaderboard": out, "live_context": ctx}


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    entries = _leaderboard_entries()
    ctx = _merged_live_context()
    st = get_live_feed_state()
    refresh = max(15, int(st.poll_interval_sec or 45))

    macro = ctx.get("macro") or {}
    cg = ctx.get("coinglass") or {}
    agents = ctx.get("agents") or []

    regime = html.escape(str(macro.get("regime", "—")))
    mreason = html.escape(str(macro.get("reasoning", ""))[:400])
    fed = html.escape(str(macro.get("fed_note", "")))
    sec_s = html.escape(str(macro.get("sec_crypto_headline_sample", ""))[:280])
    cg_ok = cg.get("ok", False)
    cg_line = html.escape(
        f"ok={cg_ok} funding={cg.get('funding_rate_avg')} OI_usd={cg.get('open_interest_usd')} "
        f"F&G={cg.get('fear_greed_value')} err={cg.get('error', '')}"[:400]
    )

    live_line = ""
    if st.updated_at:
        live_line = f"<p><b>Live feed:</b> last update <code>{html.escape(st.updated_at.isoformat())}</code> · tick {st.tick} · interval {st.poll_interval_sec:.0f}s</p>"
    if st.last_error:
        live_line += f"<p style='color:#a00'><b>Last error:</b> {html.escape(st.last_error[:300])}</p>"

    agent_rows = []
    for a in agents:
        role = html.escape(str(a.get("role", "")))
        agent_rows.append(
            "<tr>"
            f"<td>{html.escape(str(a.get('agent_id','')))}</td>"
            f"<td>{html.escape(str(a.get('name','')))}</td>"
            f"<td>{role}</td>"
            "</tr>"
        )
    agents_block = (
        "<h2>Agents</h2><table border='1' cellpadding='6'><thead><tr><th>ID</th><th>Name</th><th>Role</th></tr></thead>"
        f"<tbody>{''.join(agent_rows)}</tbody></table>"
        if agent_rows
        else "<p><em>Waiting for live agent roster…</em></p>"
    )

    if not entries:
        lb_block = "<p><em>No leaderboard (optional backtest). Live macro/CoinGlass above.</em></p>"
    else:
        rows_html = []
        for i, e in enumerate(entries):
            rows_html.append(
                "<tr>"
                f"<td>{i+1}</td>"
                f"<td>{html.escape(e.name)}</td>"
                f"<td>{e.equity_usd:,.2f}</td>"
                f"<td>{e.total_return:.2f}%</td>"
                f"<td>{e.sharpe_ratio:.3f}</td>"
                f"<td>{e.sortino_ratio:.3f}</td>"
                f"<td>{e.max_drawdown_pct:.2f}%</td>"
                f"<td>{e.diversity_factor:.3f}</td>"
                f"<td>{e.score:.4f}</td>"
                "</tr>"
            )
        lb_block = (
            "<h2>Leaderboard (trading agents)</h2>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<thead><tr><th>#</th><th>Agent</th><th>Equity</th><th>Return%</th>"
            "<th>Sharpe</th><th>Sortino</th><th>MaxDD%</th><th>Div</th><th>Score</th></tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody></table>"
        )

    macro_block = (
        f"<h2>Macro / News (global regime)</h2>{live_line}"
        f"<p><b>Market_Regime:</b> <code>{regime}</code> &nbsp; "
        f"<b>confidence:</b> {macro.get('confidence', '—')}</p>"
        f"<p>{mreason}</p>"
        f"<p><b>Fed:</b> {fed}</p>"
        f"<p><b>SEC (sample):</b> {sec_s}</p>"
    )
    cg_block = f"<h2>CoinGlass (read-only)</h2><p><code>{cg_line}</code></p>"

    head = (
        f"<head><meta charset='utf-8'><title>Alpha Arena</title>"
        f"<meta http-equiv='refresh' content='{refresh}'></head>"
    )
    intro = (
        "<!DOCTYPE html><html>"
        f"{head}<body>"
        "<h1>Alpha Arena — live data</h1>"
        "<p>This page refreshes every {}s. API keys are read from <code>.env</code> "
        "(<code>COINGLASS_API_KEY</code>, <code>FRED_API_KEY</code>).</p>".format(
            refresh
        )
    )
    tail = (
        "<p><a href='/api/leaderboard'>JSON</a> · <a href='/api/context'>context</a> · "
        "<a href='/api/live/status'>live status</a> · <a href='/health'>health</a></p>"
        "</body></html>"
    )
    return intro + f"{macro_block}{cg_block}{agents_block}{lb_block}" + tail
