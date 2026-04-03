from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx

from alpha_arena.models import MacroRegimeSignal, MarketRegime

FRED_DFF = "DFF"
SEC_RSS = "https://www.sec.gov/news/pressreleases.rss"
UA = os.getenv(
    "HTTP_USER_AGENT",
    "AlphaArenaMacroBot/1.0 (research; +https://github.com/)",
)


async def _fred_dff_latest_and_delta() -> tuple[float | None, float | None, str]:
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        return None, None, "FRED_API_KEY not set — Fed series skipped"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": FRED_DFF,
                    "api_key": key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 3,
                },
            )
            r.raise_for_status()
            obs = r.json().get("observations", [])
            vals: list[float] = []
            for o in obs:
                v = o.get("value")
                if v and v != ".":
                    vals.append(float(v))
            if not vals:
                return None, None, "FRED: empty observations"
            latest = vals[0]
            delta = (vals[0] - vals[1]) if len(vals) >= 2 else None
            note = f"DFF latest={latest:.4f}%"
            if delta is not None:
                note += f" Δ1d={delta:+.4f}pp"
            return latest, delta, note
    except Exception as e:
        return None, None, f"FRED error: {e!s}"


async def _sec_crypto_headlines(max_items: int = 12) -> tuple[str, str]:
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": UA, "Accept": "application/rss+xml,*/*"},
        ) as client:
            r = await client.get(SEC_RSS)
            r.raise_for_status()
            text = r.text
        root = ET.fromstring(text)
        titles: list[str] = []
        for item in root.findall(".//item")[:40]:
            t = item.findtext("title")
            if t:
                titles.append(t.strip())
        kw = re.compile(
            r"crypto|bitcoin|ethereum|digital asset|token|blockchain|defi|ETF",
            re.I,
        )
        neg = re.compile(
            r"enforcement|charge|fraud|lawsuit|settlement|action against|cease",
            re.I,
        )
        crypto_hits = [t for t in titles if kw.search(t)]
        neg_hits = [t for t in crypto_hits if neg.search(t)]
        sample = " | ".join((neg_hits or crypto_hits)[:max_items])
        return sample, f"SEC crypto headlines={len(crypto_hits)} enforcement_tone={len(neg_hits)}"
    except Exception as e:
        return "", f"SEC RSS error: {e!s}"


def _score_to_regime(
    fed_delta: float | None,
    sec_neg_ratio: float,
    fear_greed: int | None,
) -> tuple[MarketRegime, float, str]:
    score = 0.0
    bits: list[str] = []
    if fed_delta is not None:
        if fed_delta > 0.08:
            score -= 0.45
            bits.append("Fed effective rate up (hawkish)")
        elif fed_delta < -0.05:
            score += 0.35
            bits.append("Fed effective rate down (dovish)")
    if sec_neg_ratio >= 0.25:
        score -= 0.5
        bits.append("Heavy SEC enforcement tone")
    elif sec_neg_ratio > 0:
        score -= 0.2 * min(1.0, sec_neg_ratio * 2)
        bits.append("Some SEC enforcement headlines")
    if fear_greed is not None:
        if fear_greed < 25:
            score -= 0.15
            bits.append("Extreme fear (F&G)")
        elif fear_greed > 75:
            score += 0.1
            bits.append("Extreme greed (F&G)")

    if score >= 0.15:
        regime: MarketRegime = "risk_on"
    elif score <= -0.15:
        regime = "risk_off"
    else:
        regime = "neutral"
    conf = min(0.95, 0.45 + abs(score) * 0.9)
    return regime, conf, "; ".join(bits) or "mixed / low-conviction macro"


class MacroNewsAgent:
    """
    Fed (FRED DFF) + SEC press-release headlines (crypto-related) → Market_Regime.
    `fear_greed` optional (e.g. from CoinGlass) to blend risk sentiment.
    """

    def __init__(self, agent_id: str = "macro_news", name: str = "Macro/News Agent") -> None:
        self.agent_id = agent_id
        self.name = name

    async def compute_regime(self, *, fear_greed: int | None = None) -> MacroRegimeSignal:
        fed_val, fed_delta, fed_note = await _fred_dff_latest_and_delta()
        sec_text, sec_meta = await _sec_crypto_headlines()
        neg_kw = re.compile(
            r"enforcement|charge|fraud|lawsuit|settlement|action against|cease",
            re.I,
        )
        crypto_kw = re.compile(
            r"crypto|bitcoin|ethereum|digital asset|token|blockchain|defi|ETF",
            re.I,
        )
        titles = [t.strip() for t in sec_text.split("|") if t.strip()] if sec_text else []
        crypto_titles = [t for t in titles if crypto_kw.search(t)]
        neg_titles = [t for t in crypto_titles if neg_kw.search(t)]
        sec_neg_ratio = (len(neg_titles) / len(crypto_titles)) if crypto_titles else 0.0

        regime, conf, reasoning = _score_to_regime(fed_delta, sec_neg_ratio, fear_greed)
        return MacroRegimeSignal(
            regime=regime,
            confidence=conf,
            reasoning=reasoning,
            fed_effective_rate_pct=fed_val,
            fed_note=fed_note,
            sec_crypto_headline_sample=sec_text[:1200] if sec_text else "",
            sources=[fed_note, sec_meta],
        )
