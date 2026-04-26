"""JOTA (jota.info) — Brazilian legal/policy journalism.

Discovery via monthly sitemap XML keyword scan (sitemap.jota.info).
Article text is embedded in __NEXT_DATA__ JSON as pageProps.post.content.
PRO articles require authentication — uses Chrome cookies (rookiepy) when
available, otherwise marks empty-content articles as paywalled.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from bs4 import BeautifulSoup

from newsbr.http import make_chrome_session, make_session
from newsbr.schema import Article

NAME = "JOTA"
DOMAIN = "jota.info"
STATUS = "working"
SEARCH = "sitemap"

SITEMAP_INDEX = "https://sitemap.jota.info/sitemap-index.xml"


def search(query: str, max_pages: int = 1) -> list[Article]:
    """Scan JOTA monthly sitemaps for query keyword matches in URL slugs.

    max_pages controls how many years back to scan (1 = current year,
    3 = last 3 years). Each monthly sitemap has ~300–500 articles.
    """
    from datetime import datetime

    tokens = _query_to_keywords(query)
    if not tokens:
        return []
    year_to = datetime.now().year
    year_from = year_to - max(0, max_pages - 1)
    urls = discover_sitemap(keywords=tokens, year_from=year_from, year_to=year_to)
    return [Article(url=u, outlet=NAME) for u in urls]


def _query_to_keywords(query: str) -> list[str]:
    """Extract searchable tokens from query. Drops short words and
    normalises accented characters for slug matching."""
    raw = [t for t in re.findall(r"\w+", query.lower()) if len(t) >= 4]
    # Also add accent-stripped versions for slug matching
    out = list(raw)
    for t in raw:
        stripped = _strip_accents(t)
        if stripped != t and stripped not in out:
            out.append(stripped)
    return out


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def discover_sitemap(keywords: list[str], year_from: int = 2014,
                     year_to: int = 2026, workers: int = 8) -> list[str]:
    """Scan JOTA's monthly sitemaps for URLs matching slug keywords.

    Requires at least 2 keyword matches (or all, if fewer than 2 tokens)
    to suppress false positives from common words.
    """
    session = make_session()
    try:
        resp = session.get(SITEMAP_INDEX, timeout=30)
        resp.raise_for_status()
    except Exception:
        return []

    locs = re.findall(r"<loc>(.*?)</loc>", resp.text)
    monthly = []
    for url in locs:
        m = re.search(r"/(\d{4})/", url)
        if m and year_from <= int(m.group(1)) <= year_to:
            monthly.append(url)

    min_match = max(1, min(2, len(keywords)))
    matches = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scan_one, url, keywords, min_match): url
                   for url in monthly}
        for future in as_completed(futures):
            matches.extend(future.result())

    seen = set()
    unique = []
    for u in matches:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _scan_one(url: str, keywords: list[str], min_match: int) -> list[str]:
    try:
        resp = make_session().get(url, timeout=15)
        resp.raise_for_status()
    except Exception:
        return []
    article_urls = re.findall(
        r"<loc>(https://www\.jota\.info/[^<]+)</loc>", resp.text
    )
    out = []
    for u in article_urls:
        slug = u.lower()
        hits = sum(1 for k in keywords if k in slug)
        if hits >= min_match:
            out.append(u)
    return out


def _make_session() -> "requests.Session":
    """Session with Chrome cookies if available, plain HTTP otherwise."""
    try:
        return make_chrome_session(domains=[
            ".jota.info", "jota.info", "www.jota.info",
        ])
    except RuntimeError:
        return make_session()


def fetch(url: str) -> Optional[Article]:
    """Fetch a JOTA article. Extracts text from __NEXT_DATA__ JSON.

    Returns None if the article body is too short (< 300 chars) or if
    the page can't be fetched. PRO articles without auth return empty
    content — these are marked paywalled and skipped.
    """
    session = _make_session()
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    html = resp.text

    # Try __NEXT_DATA__ extraction first (primary path)
    article = _extract_next_data(html, url)
    if article:
        return article

    # Fallback: parse raw HTML
    return _extract_html(html, url)


def _extract_next_data(html: str, url: str) -> Optional[Article]:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        return None

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    post = data.get("props", {}).get("pageProps", {}).get("post", {})
    if not post:
        return None

    title = post.get("title", "")
    content_html = post.get("content", "")
    date = post.get("date", "")[:10]  # YYYY-MM-DD

    if not content_html or len(content_html) < 50:
        # PRO article with no content — paywalled
        return None

    # Parse HTML content to plain text
    soup = BeautifulSoup(content_html, "html.parser")
    paragraphs = []
    for p in soup.find_all(["p", "h2", "h3", "h4", "blockquote"]):
        t = p.get_text(strip=True)
        if len(t) < 10:
            continue
        if p.name in ("h2", "h3", "h4"):
            paragraphs.append(f"\n{t}\n")
        else:
            paragraphs.append(t)

    text_parts = [title, date, ""] + paragraphs if title else paragraphs
    text = "\n\n".join(text_parts)
    if len(text) < 300:
        return None

    summary = " ".join(paragraphs[:2])[:300]
    return Article(
        url=url, outlet=NAME, title=title, date=date,
        summary=summary, paywalled="no", text=text,
    )


def _extract_html(html: str, url: str) -> Optional[Article]:
    """Fallback extraction from raw HTML (for pages without __NEXT_DATA__)."""
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    og = soup.find("meta", property="og:title")
    if og:
        title = og.get("content", "")
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    date = ""
    for pat in [
        r'<meta property="article:published_time" content="([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
    ]:
        m = re.search(pat, html)
        if m:
            date = m.group(1)[:10]
            break

    for tag in soup.select(
        "script, style, nav, footer, header, aside, "
        ".paywall, .newsletter, .related, .social-share, .ad"
    ):
        tag.decompose()

    body = soup.select_one("article") or soup.select_one("div.content")
    if not body:
        return None

    parts = [title, date, ""] if title else []
    for p in body.find_all(["p", "h2", "h3", "h4"]):
        t = p.get_text(strip=True)
        if len(t) < 10:
            continue
        parts.append(f"\n{t}\n" if p.name in ("h2", "h3", "h4") else t)

    text = "\n\n".join(parts)
    if len(text) < 300:
        return None

    summary = " ".join(parts[3:5])[:300] if len(parts) > 4 else text[:300]
    return Article(
        url=url, outlet=NAME, title=title, date=date,
        summary=summary, paywalled="no", text=text,
    )
