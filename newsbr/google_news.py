"""Google News RSS — universal discovery fallback for any outlet.

Returns Article stubs (url, title, date, outlet) without full text. Caller
should pass the URL to the appropriate outlet module's fetch() to get text.

Google News URLs are wrapped — we resolve them lazily when fetch() is called.
"""

import re
import urllib.parse
from typing import Optional

from newsbr.http import make_session
from newsbr.schema import Article

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def resolve_url(url: str, timeout: int = 10) -> str:
    """Follow redirects on a Google News RSS link to get the canonical URL.
    Returns the original URL on failure."""
    if "news.google.com" not in url:
        return url
    try:
        resp = make_session().get(url, timeout=timeout, allow_redirects=True)
        return resp.url
    except Exception:
        return url


def search(query: str, site: Optional[str] = None, hl: str = "pt-BR",
           gl: str = "BR", max_items: int = 25, resolve: bool = False) -> list[Article]:
    """Query Google News RSS. If site is given, restrict to that domain.

    If resolve=True, follow each result's redirect to get the canonical URL.
    This costs one HTTP request per item but makes outlet routing reliable.
    """
    q = query
    if site:
        q = f"{query} site:{site}"
    params = {"q": q, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl[:2]}"}
    url = f"{GOOGLE_NEWS_RSS}?{urllib.parse.urlencode(params)}"

    session = make_session()
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return []

    items = re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL)
    articles = []
    for item in items[:max_items]:
        title = _extract_tag(item, "title")
        link = _extract_tag(item, "link")
        pub = _extract_tag(item, "pubDate")
        source = _extract_source(item) or (site or "")
        if not link:
            continue
        canonical = resolve_url(link) if resolve else link
        articles.append(Article(
            url=canonical,
            outlet=source,
            title=_clean(title),
            date=_parse_pubdate(pub),
        ))
    return articles


def _extract_tag(item: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", item, re.DOTALL)
    if not m:
        return ""
    s = m.group(1)
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL)
    return s.strip()


def _extract_source(item: str) -> str:
    m = re.search(r'<source[^>]*>(.*?)</source>', item, re.DOTALL)
    return _clean(m.group(1)) if m else ""


def _clean(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.DOTALL)
    return s.strip()


def _parse_pubdate(s: str) -> str:
    """RFC822 date → YYYY-MM-DD."""
    if not s:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return ""
