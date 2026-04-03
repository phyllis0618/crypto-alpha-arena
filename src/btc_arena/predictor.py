from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests

from btc_arena.models import Prediction, UnifiedMarketSnapshot


def predict_rules(snap: UnifiedMarketSnapshot) -> Prediction:
    """Single rule engine: momentum + volume + CoinGlass funding/F&G as features."""
    c = snap.candles  # bar interval from CoinGlass (e.g. 4h)
    if len(c) < 3:
        return Prediction(
            direction="FLAT",
            confidence=0.2,
            pred_return_next=0.0,
            reasoning="insufficient candles",
            model="rules",
        )
    last = c[-1].close
    prev = c[-2].close
    r1 = last / prev - 1.0 if prev else 0.0
    r5 = last / c[-6].close - 1.0 if len(c) >= 6 else r1
    vol_bar = c[-1].volume * last
    snap.volume_usd_last_bar = vol_bar

    cg = snap.coinglass
    fund = cg.funding_rate_avg or 0.0
    fg = cg.fear_greed
    fg_adj = 0.0
    if fg is not None:
        if fg < 30:
            fg_adj = -0.0003
        elif fg > 70:
            fg_adj = 0.0002

    edge = 0.55 * r5 + 0.35 * r1 + 0.15 * fund + fg_adj
    if os.getenv("BTC_ARENA_USE_MACRO", "1").strip().lower() not in ("0", "false", "no"):
        m = snap.macro
        if m and m.regime in ("risk_on", "risk_off"):
            w = float(os.getenv("BTC_ARENA_MACRO_EDGE_WEIGHT", "0.00012"))
            if m.regime == "risk_on":
                edge += w
            else:
                edge -= w
    if abs(edge) < 0.00025:
        return Prediction(
            direction="FLAT",
            confidence=0.25,
            pred_return_next=edge,
            reasoning=f"edge={edge:.6f} r1={r1:.5f} r5={r5:.5f} fund={fund:.6f} macro={snap.macro.regime}",
            model="rules",
        )
    direction = "UP" if edge > 0 else "DOWN"
    conf = min(0.92, 0.35 + min(abs(edge) * 120.0, 0.55))
    return Prediction(
        direction=direction,
        confidence=conf,
        pred_return_next=edge,
        reasoning=f"edge={edge:.6f} r1={r1:.5f} r5={r5:.5f} vol~${vol_bar:,.0f} fund={fund:.6f} fg={fg} macro={snap.macro.regime}",
        model="rules",
    )


def _parse_json_from_llm_text(raw: str) -> dict:
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
    return json.loads(text)


def predict_ollama(snap: UnifiedMarketSnapshot) -> Optional[Prediction]:
    """
    Local Llama via Ollama HTTP API (no cloud API key).
    Requires Ollama running: https://ollama.com — e.g. `ollama pull llama3.2`
    """
    base = os.getenv("BTC_ARENA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("BTC_ARENA_OLLAMA_MODEL", "llama3.2").strip()
    iv = snap.bar_interval or "4h"
    payload = {
        "market": snap.market.model_dump(mode="json"),
        "bar_interval": iv,
        "ret_last_bar": snap.ret_last_bar,
        "ret_5bars": snap.ret_5bars,
        "coinglass": snap.coinglass.model_dump(),
        "macro": snap.macro.model_dump(mode="json"),
        "social_tweets_n": len(snap.social.tweets),
        "candles_tail": [x.model_dump(mode="json") for x in snap.candles[-12:]],
    }
    sys_prompt = (
        f"You forecast the NEXT bar's BTC futures simple return (close_next/close_now - 1). "
        f"Each candle is {iv}. Output one JSON object only, no markdown: "
        '{"direction":"UP"|"DOWN"|"FLAT","confidence":0-1,"pred_return_next":float,"reasoning":"brief"}'
    )
    try:
        r = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "stream": False,
                "options": {"temperature": 0.15},
            },
            timeout=float(os.getenv("BTC_ARENA_OLLAMA_TIMEOUT", "120")),
        )
        r.raise_for_status()
        body = r.json()
        raw = (body.get("message") or {}).get("content") or ""
        data = _parse_json_from_llm_text(raw)
        return Prediction(
            direction=data["direction"],
            confidence=float(data["confidence"]),
            pred_return_next=float(data.get("pred_return_next", 0)),
            reasoning=str(data.get("reasoning", ""))[:500],
            model=f"ollama:{model}",
        )
    except Exception:
        return None


def predict_single_model(snap: UnifiedMarketSnapshot) -> Prediction:
    """Rules by default; local Ollama (Llama) when BTC_ARENA_USE_LLM=1."""
    if os.getenv("BTC_ARENA_USE_LLM", "").strip().lower() in ("1", "true", "yes"):
        p = predict_ollama(snap)
        if p is not None:
            return p
    return predict_rules(snap)
