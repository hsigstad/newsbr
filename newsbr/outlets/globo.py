"""O Globo (oglobo.globo.com).

Discovery via daily sitemap XML keyword scan. Fetching uses Chrome cookies
(rookiepy) to bypass the paywall.
"""

import re
import csv as _csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import html2text
from bs4 import BeautifulSoup

from newsbr import google_news
from newsbr.http import make_chrome_session, make_session
from newsbr.schema import Article

NAME = "O Globo"
DOMAIN = "oglobo.globo.com"
STATUS = "working"
SEARCH = "sitemap"

SITEMAP_INDEX = "https://oglobo.globo.com/sitemap/oglobo/sitemap.xml"

# Default URL-slug keywords. Callers can pass their own to discover_sitemap().
DEFAULT_URL_KEYWORDS = [
    "filhotismo", "nepotismo", "parente", "parentesco",
    "impedimento", "suspeicao",
    "venda-sentenca", "venda-decisao",
    "corrupcao-tribunal", "corrupcao-judiciario",
    "operacao-faroeste", "operacao-naufragio", "sisamnes",
    "banco-master",
]


def search(query: str, max_pages: int = 1) -> list[Article]:
    """Scan recent O Globo daily sitemaps for query keyword matches in
    URL slugs. max_pages controls year span back from current year
    (1 page ≈ current year only; 3 pages ≈ last 3 years).
    For a full historical scan use discover_sitemap() directly.
    """
    from datetime import datetime
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) >= 4]
    if not tokens:
        return []
    year_to = datetime.now().year
    year_from = year_to - max(0, max_pages - 1)
    urls = discover_sitemap(keywords=tokens, year_from=year_from, year_to=year_to)
    return [Article(url=u, outlet=NAME) for u in urls]


def discover_sitemap(keywords: Optional[list[str]] = None,
                     year_from: int = 2014, year_to: int = 2026,
                     workers: int = 10) -> list[str]:
    """Scan O Globo's daily sitemaps for URLs matching slug keywords."""
    keywords = keywords or DEFAULT_URL_KEYWORDS
    session = make_session()
    resp = session.get(SITEMAP_INDEX, timeout=30)
    resp.raise_for_status()
    locs = re.findall(
        r"<loc>(https://oglobo\.globo\.com/sitemap/oglobo/(\d{4})/\d{2}/\d{2}_\d+\.xml)</loc>",
        resp.text,
    )
    daily = [url for url, year in locs if year_from <= int(year) <= year_to]

    matches = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scan_one, url, keywords): url for url in daily}
        for future in as_completed(futures):
            matches.extend(future.result())

    seen = set()
    unique = []
    for u in matches:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _scan_one(url: str, keywords: list[str]) -> list[str]:
    try:
        resp = make_session().get(url, timeout=15)
        resp.raise_for_status()
    except Exception:
        return []
    article_urls = re.findall(r"<loc>(https://oglobo\.globo\.com/[^<]+)</loc>", resp.text)
    return [u for u in article_urls if any(k in u.lower() for k in keywords)]


def fetch(url: str) -> Optional[Article]:
    """Requires Chrome cookies (login). Pass through paywall."""
    try:
        session = make_chrome_session(domains=[
            ".oglobo.globo.com", ".globo.com",
            "oglobo.globo.com", "globo.com",
        ])
    except RuntimeError:
        # rookiepy unavailable — try without cookies
        session = make_session()

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    text, title, date = _extract(resp.text, url)
    if not text or len(text) < 300:
        return None

    summary = (text.split("\n\n", 2)[1] if "\n\n" in text else text)[:300]
    return Article(
        url=url, outlet=NAME, title=title, date=date,
        summary=summary, paywalled="no", text=text,
    )


def _extract(html: str, url: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "")
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    date = ""
    date_meta = soup.find("meta", property="article:published_time")
    if date_meta:
        date = date_meta.get("content", "")[:10]
    if not date:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        if m:
            date = m.group(1)[:10]

    for tag in soup.select(
        "script, style, nav, footer, header, aside, "
        ".paywall, .newsletter, .related, .comments, "
        ".social-share, .ad, .tags, .breadcrumb"
    ):
        tag.decompose()

    parts = []
    if title:
        parts.append(title)

    og_desc = soup.find("meta", property="og:description")
    if og_desc:
        desc = og_desc.get("content", "").strip()
        if desc and len(desc) > 30:
            parts.append(desc)

    if date:
        parts.append(date)
    parts.append("")

    body = (
        soup.select_one("div.article__content-container")
        or soup.select_one("div[itemprop='articleBody']")
        or soup.select_one("article")
        or soup.select_one("div.content")
    )
    skip_strings = [
        "carregando", "assine", "assinante", "copiar link",
        "salvar para ler", "recurso exclusivo", "newsletter",
        "receba no seu email", "leia mais", "continue lendo",
    ]
    if body:
        for p in body.find_all(["p", "h2", "h3", "h4"]):
            t = p.get_text(strip=True)
            if len(t) < 10 or any(s in t.lower() for s in skip_strings):
                continue
            parts.append(f"\n{t}\n" if p.name in ("h2", "h3", "h4") else t)
    else:
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = True
        h.ignore_images = True
        parts.append(h.handle(html))

    return "\n\n".join(parts).strip(), title, date
