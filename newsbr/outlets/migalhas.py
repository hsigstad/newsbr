"""Migalhas (migalhas.com.br) — Brazilian legal news. Free, no paywall.

Native search at /busca?q=... works without auth.
"""

import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup

from newsbr.http import make_session
from newsbr.outlets.conjur import fetch as _conjur_fetch  # same meta extraction
from newsbr.schema import Article

NAME = "Migalhas"
DOMAIN = "migalhas.com.br"
STATUS = "working"
SEARCH = "native"


def search(query: str, max_pages: int = 1) -> list[Article]:
    session = make_session()
    out = []
    seen = set()
    for page in range(1, max_pages + 1):
        params = {"q": query}
        if page > 1:
            params["pagina"] = page
        url = f"https://www.migalhas.com.br/busca?{urllib.parse.urlencode(params)}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        page_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/quentes/" not in href and "/depeso/" not in href:
                continue
            if href.startswith("/"):
                href = "https://www.migalhas.com.br" + href
            if DOMAIN not in href or href in seen:
                continue
            seen.add(href)
            title = a.get_text(strip=True)
            page_links.append(Article(url=href, outlet=NAME, title=title))
        if not page_links:
            break
        out.extend(page_links)
    return out


def fetch(url: str) -> Optional[Article]:
    """Same og:title / datePublished extraction as Conjur."""
    a = _conjur_fetch(url)
    if a is not None:
        a.outlet = NAME
    return a
