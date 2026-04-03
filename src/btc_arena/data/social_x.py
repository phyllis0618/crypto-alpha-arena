from __future__ import annotations

import os
from typing import Any

import httpx

from btc_arena.models import SocialXSnapshot, SocialXTweet

TWITTER_API = "https://api.twitter.com/2"


def _bearer() -> str:
    return os.getenv("TWITTER_BEARER_TOKEN", os.getenv("X_BEARER_TOKEN", "")).strip()


async def fetch_social_x_snapshot() -> SocialXSnapshot:
    """
    Recent tweets from configured usernames via Twitter / X API v2 (Bearer token).
    Requires a Twitter Developer account + app with read access; not available without a token.
    Docs: https://developer.twitter.com/en/docs/twitter-api
    """
    token = _bearer()
    if not token:
        return SocialXSnapshot(
            ok=False,
            error="not_configured",
            note="Set TWITTER_BEARER_TOKEN in .env (X Developer Portal). No unofficial scraping.",
        )

    raw = os.getenv("TWITTER_MONITOR_USERNAMES", "elonmusk")
    usernames = [u.strip().lstrip("@") for u in raw.split(",") if u.strip()][:6]
    if not usernames:
        return SocialXSnapshot(ok=False, error="no_usernames", note="Set TWITTER_MONITOR_USERNAMES")

    headers = {"Authorization": f"Bearer {token}", "User-Agent": os.getenv("HTTP_USER_AGENT", "BTCArena/1.0")}
    tweets: list[SocialXTweet] = []
    timeout = float(os.getenv("TWITTER_TIMEOUT", "20"))

    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            for uname in usernames:
                ur = await client.get(f"{TWITTER_API}/users/by/username/{uname}")
                if ur.status_code != 200:
                    continue
                uid = (ur.json().get("data") or {}).get("id")
                if not uid:
                    continue
                n = max(5, min(100, int(os.getenv("TWITTER_MAX_PER_USER", "5"))))
                tr = await client.get(
                    f"{TWITTER_API}/users/{uid}/tweets",
                    params={
                        "max_results": n,
                        "tweet.fields": "created_at,text",
                    },
                )
                if tr.status_code != 200:
                    continue
                for t in (tr.json().get("data") or [])[:5]:
                    if not isinstance(t, dict):
                        continue
                    text = t.get("text") or ""
                    tweets.append(
                        SocialXTweet(
                            username=uname,
                            text=text[:500],
                            created_at=str(t.get("created_at") or ""),
                        )
                    )
        ok = len(tweets) > 0
        return SocialXSnapshot(
            ok=ok,
            error=None if ok else "no_tweets_fetched",
            tweets=tweets,
            note="Official API v2 only; rate limits apply per Twitter tier.",
        )
    except Exception as e:
        return SocialXSnapshot(ok=False, error=type(e).__name__, note=str(e)[:200])


def social_x_snapshot_sync() -> SocialXSnapshot:
    import asyncio

    return asyncio.run(fetch_social_x_snapshot())
