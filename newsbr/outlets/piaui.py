"""Revista Piauí (piaui.folha.uol.com.br).

Sitemap-based discovery; Playwright + Chrome cookies for fetching since
Piauí relies on JS-rendered content.
"""

import re
import time
from typing import Optional
from xml.etree import ElementTree

from newsbr import google_news
from newsbr.schema import Article

NAME = "piaui"
DOMAIN = "piaui.folha.uol.com.br"
STATUS = "rss_only"     # native fetch requires playwright; only enable if installed
SEARCH = "sitemap"

SITEMAP_URLS = [
    "https://piaui.folha.uol.com.br/post-sitemap.xml",
    "https://piaui.folha.uol.com.br/post-sitemap2.xml",
    "https://piaui.folha.uol.com.br/post-sitemap3.xml",
    "https://piaui.folha.uol.com.br/post-sitemap4.xml",
]


def search(query: str, max_pages: int = 1) -> list[Article]:
    """Sitemap scan filtered by query keyword tokens. Requires playwright."""
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) >= 4]
    if not tokens:
        return []
    urls = discover_sitemap(tokens)
    return [Article(url=u, outlet=NAME) for u in urls]


def discover_sitemap(keywords: list[str]) -> list[str]:
    """Walk Piauí post sitemaps, return URLs whose slugs match any keyword.
    Requires playwright + Chrome cookies."""
    page = _new_playwright_page()
    if page is None:
        return []
    all_urls = []
    for sm in SITEMAP_URLS:
        try:
            page.goto(sm, timeout=30000)
            content = page.content()
            for m in re.finditer(r'<loc>\s*(https?://[^<]+)\s*</loc>', content):
                all_urls.append(m.group(1))
        except Exception:
            continue
    return [u for u in all_urls if any(k in u.lower() for k in keywords)]


def fetch(url: str) -> Optional[Article]:
    page = _new_playwright_page()
    if page is None:
        return None
    try:
        page.goto(url, timeout=30000)
        time.sleep(2)
        title = ""
        title_el = page.query_selector("h1")
        if title_el:
            title = title_el.inner_text().strip()

        body = ""
        for sel in [".post-content", ".entry-content", "article", ".content-text"]:
            el = page.query_selector(sel)
            if el:
                body = el.inner_text().strip()
                if len(body) > 200:
                    break
        if not body:
            body = page.inner_text("body")

        text = (title + "\n\n" + body).strip() if title else body
        if len(text) < 200:
            return None
        return Article(
            url=url, outlet=NAME, title=title, date="",
            summary=body[:300], paywalled="no", text=text,
        )
    except Exception:
        return None


def _new_playwright_page():
    """Open a Playwright page with Chrome cookies. Returns None if unavailable."""
    try:
        from playwright.sync_api import sync_playwright
        import rookiepy
    except ImportError:
        return None
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        cookies = rookiepy.chrome(domains=[
            ".folha.uol.com.br", ".uol.com.br",
            "piaui.folha.uol.com.br", "folha.uol.com.br",
        ])
        pw_cookies = []
        for c in cookies:
            cookie = {
                "name": c["name"], "value": c["value"],
                "domain": c.get("domain", ""), "path": c.get("path", "/"),
            }
            if c.get("expires"):
                cookie["expires"] = c["expires"]
            pw_cookies.append(cookie)
        context.add_cookies(pw_cookies)
        return context.new_page()
    except Exception:
        return None
