"""Conjur (conjur.com.br) — Brazilian legal news. Free, no paywall."""

import re
from typing import Optional

from newsbr import google_news
from newsbr.http import make_session, html_to_text
from newsbr.schema import Article

NAME = "Conjur"
DOMAIN = "conjur.com.br"
STATUS = "working"
SEARCH = "google_news"


def search(query: str, max_pages: int = 1) -> list[Article]:
    """Discover via Google News with site:conjur.com.br."""
    items = google_news.search(query, site=DOMAIN, max_items=25 * max_pages, resolve=True)
    items = [a for a in items if DOMAIN in a.url]
    for a in items:
        a.outlet = NAME
    return items


def fetch(url: str) -> Optional[Article]:
    """Fetch full article. Conjur has og:title, datePublished meta tags."""
    session = make_session()
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    html = resp.text
    title = _meta(html, "og:title") or _title_tag(html)
    date = _date(html)
    text = html_to_text(html)
    if len(text) < 300:
        return None

    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 30]
    summary = " ".join(lines[1:4])[:300] if len(lines) > 1 else (lines[0][:300] if lines else "")

    return Article(
        url=url, outlet=NAME, title=title, date=date,
        summary=summary, paywalled="no", text=text,
    )


def _meta(html: str, prop: str) -> str:
    m = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]+)"', html)
    return m.group(1) if m else ""


def _title_tag(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html)
    if not m:
        return ""
    return m.group(1).split(" - ")[0].split(" | ")[0].strip()


def _date(html: str) -> str:
    for pat in [
        r'<meta property="article:published_time" content="([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'<time[^>]*datetime="([^"]+)"',
    ]:
        m = re.search(pat, html)
        if m:
            return m.group(1)[:10]
    return ""
