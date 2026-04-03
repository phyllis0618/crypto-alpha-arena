"""Shared aiohttp helpers: retries for flaky servers (connection reset, etc.)."""

from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, Optional, TypeVar

import aiohttp

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

T = TypeVar("T")

# Errno 54 (macOS) / ECONNRESET: wrapped as ClientOSError → ClientConnectionError
_RETRYABLE_EXC = (
    aiohttp.ClientConnectionError,
    aiohttp.ServerDisconnectedError,
    asyncio.TimeoutError,
)

# AMAC / front proxies often return transient 502/503; 429 = throttle
RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({429, 502, 503, 504})


def create_connector(*, limit: int = 40, limit_per_host: int = 8) -> aiohttp.TCPConnector:
    """Fresh connections; cleanup helps when the peer resets idle TLS sockets."""
    return aiohttp.TCPConnector(
        limit=limit,
        limit_per_host=limit_per_host,
        enable_cleanup_closed=True,
    )


def default_timeout(total: float = 60.0) -> aiohttp.ClientTimeout:
    return aiohttp.ClientTimeout(total=total, connect=20, sock_read=45)


async def async_retry(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = 5,
    base_delay_s: float = 1.0,
    max_delay_s: float = 45.0,
    retry_http_statuses: Optional[frozenset[int]] = None,
) -> T:
    """Retry transient network failures and optional HTTP status codes (502, etc.)."""
    delay = base_delay_s
    last: Optional[BaseException] = None
    for i in range(attempts):
        try:
            return await op()
        except aiohttp.ClientResponseError as exc:
            if not retry_http_statuses or exc.status not in retry_http_statuses:
                raise
            last = exc
            if i == attempts - 1:
                raise
            jitter = random.uniform(0, min(2.0, delay * 0.25))
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2.0, max_delay_s)
        except _RETRYABLE_EXC as exc:
            last = exc
            if i == attempts - 1:
                raise
            jitter = random.uniform(0, min(2.0, delay * 0.25))
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2.0, max_delay_s)
    assert last is not None
    raise last


async def fetch_text(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout: float = 60.0,
    attempts: int = 5,
    extra_headers: Optional[dict[str, str]] = None,
) -> str:
    headers = {"User-Agent": DEFAULT_UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
    if extra_headers:
        headers.update(extra_headers)
    to = aiohttp.ClientTimeout(total=timeout, connect=20, sock_read=min(40.0, timeout))

    async def once() -> str:
        async with session.get(url, headers=headers, timeout=to, allow_redirects=True) as resp:
            resp.raise_for_status()
            return await resp.text(encoding="utf-8", errors="replace")

    return await async_retry(once, attempts=attempts, retry_http_statuses=RETRYABLE_HTTP_STATUSES)


async def fetch_json_post(
    session: aiohttp.ClientSession,
    url: str,
    *,
    json_body: Any = None,
    timeout: float = 60.0,
    attempts: int = 5,
) -> Any:
    headers = {
        "User-Agent": DEFAULT_UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    to = aiohttp.ClientTimeout(total=timeout, connect=20, sock_read=min(40.0, timeout))

    async def once() -> Any:
        async with session.post(url, json=json_body if json_body is not None else {}, headers=headers, timeout=to) as resp:
            resp.raise_for_status()
            return await resp.json()

    return await async_retry(once, attempts=attempts, retry_http_statuses=RETRYABLE_HTTP_STATUSES)
