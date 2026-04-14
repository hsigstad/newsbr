"""Estadão (estadao.com.br).

Estadão's paywall is JS-only — full article text is in the initial HTML
response as <p> tags. Simple HTTP requests work without executing JS.

Discovery: RSS feed by default (filters items by query keyword in title).
Topic-page crawling is available via discover_topic() but is opt-in —
each topic page is project-specific and shouldn't be wired into the
default search path.
"""

import re
from typing import Optional

from newsbr.http import make_session
from newsbr.schema import Article

NAME = "Estadao"
DOMAIN = "estadao.com.br"
STATUS = "working"
SEARCH = "rss"

RSS_URL = "https://www.estadao.com.br/arc/outboundfeeds/rss/?outputType=xml"


def search(query: str, max_pages: int = 1, topic_pages: Optional[list[str]] = None) -> list[Article]:
    """Discover Estadão articles relevant to a query.

    By default scans only the site-wide RSS feed and filters items whose
    titles contain any query token of length ≥ 4. Pass `topic_pages` to
    additionally crawl one or more `tudo-sobre/<topic>/` pages — useful
    for project-specific beats. Topic-page results are filtered by URL
    slug match against the same tokens, which is noisier than RSS title
    matching, so use sparingly.
    """
    keywords = _query_to_keywords(query)
    if not keywords:
        return []
    seen = set()
    out = []
    for url in discover_rss(keywords):
        if url not in seen:
            seen.add(url)
            out.append(Article(url=url, outlet=NAME))
    for topic in (topic_pages or []):
        for url in discover_topic(topic, keywords):
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
    """Scan the Estadão RSS feed for items whose title matches the query.

    To suppress single-keyword false positives (e.g. a query token like
    `massa` matching an immigration headline), require at least two
    distinct query tokens in the title — or all tokens, if the query
    has fewer than two. URL paths under nutrition/lifestyle subsections
    are also dropped.
    """
    session = make_session()
    try:
        resp = session.get(RSS_URL, timeout=30)
        resp.raise_for_status()
    except Exception:
        return []
    items = re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL)
    min_match = max(1, min(2, len(keywords)))
    out = []
    for item in items:
        title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item)
        link_m = re.search(r"<link>(https://[^<]+)</link>", item)
        if not (title_m and link_m):
            continue
        link = link_m.group(1)
        if any(seg in link for seg in ("/pulsa/", "/web-stories/", "/nutricao/")):
            continue
        title = title_m.group(1).lower()
        matches = sum(1 for k in keywords if k in title)
        if matches >= min_match:
            out.append(link)
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
