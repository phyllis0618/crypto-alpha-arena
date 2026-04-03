from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from btc_arena.models import UnifiedMarketSnapshot


def _market_summary(snap: UnifiedMarketSnapshot | None) -> str:
    if snap is None:
        return ""
    m = snap.market
    a = snap.analytics
    mac = snap.macro
    lines = [
        f"BTC last={m.last_price:,.2f} 24h%={m.price_change_pct_24h:+.2f}",
        f"bars={a.n_bars} interval={snap.bar_interval} vol_usd_last={a.volume_usd_last:,.0f} vol_ratio={a.volume_ratio_vs_sma}",
        f"RSI14={a.rsi_14} F&G={snap.coinglass.fear_greed} funding={snap.coinglass.funding_rate_avg}",
        f"macro={mac.regime} Fed={mac.fed_note[:80] if mac.fed_note else '—'}",
    ]
    return " | ".join(str(x) for x in lines)


def _ollama_chat(system: str, user: str) -> str:
    base = os.getenv("BTC_ARENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("BTC_ARENA_OLLAMA_MODEL", "llama3.2").strip()
    r = requests.post(
        f"{base}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=float(os.getenv("BTC_ARENA_OLLAMA_TIMEOUT", "120")),
    )
    r.raise_for_status()
    return (r.json().get("message") or {}).get("content") or ""


def _format_llm_rumor_output(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:].lstrip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return raw


def _validate_rumors_ollama(extraction_json: str, user_text: str, snap: UnifiedMarketSnapshot | None) -> str:
    """Second agent: turn extracted claims into a validated rumor-signal (advisory only)."""
    ctx = _market_summary(snap)
    sys_prompt = (
        "You are a validation agent. Given extraction JSON from another model plus the same user text, "
        "check each claim against the market context (numbers are hints, not ground truth). "
        "Output JSON only, no markdown: "
        '{"rumor_signal":"ignore|watch|elevated","strength":0-1,"items":['
        '{"claim":"","verdict":"unverified|plausible|conflicts_context|likely_noise","note":""}],'
        '"summary":""}'
    )
    user_block = (
        f"Market context:\n{ctx}\n\nExtraction JSON:\n{extraction_json}\n\nOriginal user text:\n{user_text}"
    )
    raw = _ollama_chat(sys_prompt, user_block)
    return _format_llm_rumor_output(raw)


def extract_rumors_ollama(user_text: str, snap: UnifiedMarketSnapshot | None) -> str:
    """Rumor extract agent (+ optional validation agent) — advisory; does not change trade direction."""
    base = os.getenv("BTC_ARENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("BTC_ARENA_OLLAMA_MODEL", "llama3.2").strip()
    ctx = _market_summary(snap)
    sys_prompt = (
        "You analyze crypto trader chatter. Identify unverified claims, hearsay, speculation, and "
        "possible misinformation. Output compact JSON only (no markdown fences): "
        '{"rumors":[{"text":"","risk":"low|medium|high"}],"entities":[],"notes":""} '
        "If nothing rumor-like, use empty rumors array."
    )
    user_block = f"Context (market snapshot, may be incomplete):\n{ctx}\n\nUser message:\n{user_text}"
    try:
        r = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_block},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=float(os.getenv("BTC_ARENA_OLLAMA_TIMEOUT", "120")),
        )
        r.raise_for_status()
        raw = (r.json().get("message") or {}).get("content") or ""
        extracted = _format_llm_rumor_output(raw)
        if os.getenv("BTC_ARENA_RUMOR_VALIDATE", "1").strip().lower() in ("0", "false", "no"):
            return extracted
        try:
            validated = _validate_rumors_ollama(extracted, user_text, snap)
            return (
                "=== Rumor extract agent ===\n"
                + extracted
                + "\n\n=== Rumor validation agent (signal) ===\n"
                + validated
            )
        except Exception as ve:
            return extracted + f"\n\n(validation agent skipped: {ve!s})"
    except Exception as e:
        return fallback_rumor_scan(user_text) + f"\n\n(Ollama unavailable: {e!s})"


def fallback_rumor_scan(text: str) -> str:
    """Heuristic scan when Ollama is down."""
    t = text.lower()
    keywords = [
        "rumor",
        "heard",
        "allegedly",
        "unconfirmed",
        "insider",
        "whale",
        "pump",
        "hack",
        "sec",
        "etf",
        "listing",
    ]
    hits = [k for k in keywords if k in t]
    out: dict[str, Any] = {
        "rumors": [{"text": text[:500], "risk": "medium" if hits else "low"}],
        "keyword_hits": hits,
        "notes": "Heuristic scan only — start Ollama for structured extraction.",
    }
    return json.dumps(out, ensure_ascii=False, indent=2)
