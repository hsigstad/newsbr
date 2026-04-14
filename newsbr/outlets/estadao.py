"""Estadão (estadao.com.br).

Estadão's paywall is JS-only — full article text is in the initial HTML
response as <p> tags. Simple HTTP requests work without executing JS.
Discovery via topic pages + RSS, fallback to Google News.
"""

import re
from typing import Optional

from newsbr import google_news
from newsbr.http import make_session
from newsbr.schema import Article

NAME = "Estadao"
DOMAIN = "estadao.com.br"
STATUS = "working"
SEARCH = "topic+rss"

TOPIC_PAGES = [
    "https://www.estadao.com.br/tudo-sobre/nepotismo/",
    "https://www.estadao.com.br/tudo-sobre/stf/",
    "https://www.estadao.com.br/tudo-sobre/judiciario/",
    "https://www.estadao.com.br/tudo-sobre/corrupcao/",
]
RSS_URL = "https://www.estadao.com.br/arc/outboundfeeds/rss/?outputType=xml"


def search(query: str, max_pages: int = 1) -> list[Article]:
    """Discover via topic pages + RSS, filtered by query keyword tokens.
    Estadão has no public query-string search API."""
    keywords = _query_to_keywords(query)
    if not keywords:
        return []
    seen = set()
    out = []
    for topic in TOPIC_PAGES:
        for url in discover_topic(topic, keywords):
            if url not in seen:
                seen.add(url)
                out.append(Article(url=url, outlet=NAME))
    for url in discover_rss(keywords):
        if url not in seen:
            seen.add(url)
            out.append(Article(url=url, outlet=NAME))
    return out


def _query_to_keywords(query: str) -> list[str]:
    return [t for t in re.findall(r"\w+", query.lower()) if len(t) >= 4]


def discover_topic(topic_url: str, keywords: list[str]) -> list[str]:
    """Pull article URLs from a tudo-sobre topic page, filtered by keywords."""
    session = make_session()
    try:
        resp = session.get(topic_url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return []
    urls = re.findall(
        r'href="(https://www\.estadao\.com\.br/(?:politica|brasil|economia)/[^"]+)"',
        resp.text,
    )
    urls = [u for u in set(urls) if u.count("/") >= 5]
    if keywords:
        urls = [u for u in urls if any(k in u.lower() for k in keywords)]
    return urls


def discover_rss(keywords: list[str]) -> list[str]:
    session = make_session()
    try:
        resp = session.get(RSS_URL, timeout=30)
        resp.raise_for_status()
    except Exception:
        return []
    items = re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL)
    out = []
    for item in items:
        title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item)
        link_m = re.search(r"<link>(https://[^<]+)</link>", item)
        if title_m and link_m:
            title = title_m.group(1).lower()
            if not keywords or any(k in title for k in keywords):
                out.append(link_m.group(1))
    return out


def fetch(url: str) -> Optional[Article]:
    session = make_session()
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None
    html = resp.text

    title = _meta(html, "og:title")
    if not title:
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            title = m.group(1).split(" - ")[0].strip()

    date = ""
    for pat in [
        r'<meta property="article:published_time" content="([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pat, html)
        if m:
            date = m.group(1)[:10]
            break

    p_tags = re.findall(r"<p[^>]*>(.+?)</p>", html, re.DOTALL)
    paragraphs = [
        re.sub(r"<[^>]+>", "", p).strip()
        for p in p_tags
        if len(re.sub(r"<[^>]+>", "", p).strip()) > 50
    ]
    if len(paragraphs) < 3:
        return None

    body = paragraphs[1:-2] if len(paragraphs) > 5 else paragraphs
    text = "\n\n".join(body)
    if len(text) < 200:
        return None

    summary = " ".join(body[:2])[:300]
    return Article(
        url=url, outlet=NAME, title=title, date=date,
        summary=summary, paywalled="no", text=text,
    )


def _meta(html: str, prop: str) -> str:
    m = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]+)"', html)
    return m.group(1) if m else ""
