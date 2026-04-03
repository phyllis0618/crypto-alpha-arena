"""Async scrape of Yanfu public consult / announcements (no login)."""

from __future__ import annotations

import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from yanfu_global_research.http_utils import DEFAULT_UA, create_connector, fetch_text

YANFU_CONSULT_URL = "https://yanfuinvestments.com/consult"


async def fetch_consult_html(session: aiohttp.ClientSession) -> str:
    return await fetch_text(session, YANFU_CONSULT_URL, timeout=40.0, attempts=5)


def parse_consult_announcements(html: str) -> list[dict[str, str]]:
    """
    Next.js often embeds list in static HTML; fallback regex for known class hooks.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, str]] = []

    # Try CSS module class fragments seen historically on site
    for card in soup.select('[class*="consult_container_right_content"]'):
        text_el = card.select_one('[class*="page_text"]')
        month_el = card.select_one('[class*="page_mounth"]')
        year_el = card.select_one('[class*="page_year"]')
        if text_el and month_el and year_el:
            title = text_el.get_text(strip=True)
            mo = month_el.get_text(strip=True)
            yr = year_el.get_text(strip=True)
            if title:
                out.append({"date": f"{yr}-{mo.replace('/', '-')}", "title": title})

    if out:
        return out

    blocks = re.findall(
        r'page_mounth__[^"]*">(\d+/\d+)</div><div class="page_year__[^"]*">(\d{4})</div>'
        r'.*?page_text__[^"]*">([^<]+)</div>',
        html,
        re.DOTALL,
    )
    for m, y, title in blocks:
        out.append({"date": f"{y}-{m.replace('/', '-')}", "title": title.strip()})
    return out


async def scrape_yanfu_consult_public() -> dict[str, Any]:
    connector = create_connector()
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": DEFAULT_UA}) as session:
        html = await fetch_consult_html(session)
    items = parse_consult_announcements(html)
    return {
        "source": "yanfu_official_consult_async",
        "url": YANFU_CONSULT_URL,
        "announcementCount": len(items),
        "announcements": items,
    }
