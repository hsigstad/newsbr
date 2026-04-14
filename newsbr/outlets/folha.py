"""Folha de S.Paulo (folha.uol.com.br).

Native search via search.folha.uol.com.br. Fetching uses Chrome cookies
(rookiepy) to bypass the paywall.
"""

import re
import urllib.parse
from typing import Optional

import html2text
from bs4 import BeautifulSoup

from newsbr.http import make_chrome_session, make_session
from newsbr.schema import Article

NAME = "Folha de S.Paulo"
DOMAIN = "folha.uol.com.br"
STATUS = "working"
SEARCH = "native"


def search(query: str, max_pages: int = 1) -> list[Article]:
    """Folha's native search. Returns Article stubs (url, title, date)."""
    try:
        session = make_chrome_session(domains=[
            ".folha.uol.com.br", ".uol.com.br",
            "folha.uol.com.br", "uol.com.br",
        ])
    except RuntimeError:
        session = make_session()

    out = []
    for page in range(1, max_pages + 1):
        offset = (page - 1) * 25 + 1 if page > 1 else ""
        url = (
            f"https://search.folha.uol.com.br/search?q={urllib.parse.quote(query)}"
            f"&site=todos&periodo=todos&results_count=25&search_time=1&url=&sr={offset}"
        )
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        page_results = []
        for item in soup.select("li.c-headline"):
            links = item.select("a[href*='folha.uol.com.br']")
            href, title = "", ""
            for link in links:
                h = link.get("href", "")
                t = link.get_text(strip=True)
                if h:
                    href = h
                if t:
                    title = t
            date_str = ""
            date_el = item.select_one("time, .c-headline__dateline")
            if date_el:
                date_str = date_el.get_text(strip=True)
            if href and title and "folha.uol.com.br" in href:
                page_results.append(Article(
                    url=href.split("?")[0],
                    outlet=NAME,
                    title=title,
                    date=_parse_folha_date(date_str),
                ))
        if not page_results:
            break
        out.extend(page_results)
    return out


def fetch(url: str) -> Optional[Article]:
    try:
        session = make_chrome_session(domains=[
            ".folha.uol.com.br", ".uol.com.br",
            "folha.uol.com.br", "uol.com.br",
        ])
    except RuntimeError:
        session = make_session()

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    text, title, date_str = _extract(resp.text)
    if len(text) < 300:
        return None

    return Article(
        url=url, outlet=NAME, title=title, date=_parse_folha_date(date_str),
        summary=(text.split("\n\n", 2)[1] if "\n\n" in text else text)[:300],
        paywalled="no", text=text,
    )


def _extract(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, nav, footer, header, .c-news__sidebar, "
                           ".c-related, .c-newsletter, .c-paywall, .c-most-read, "
                           ".c-ad, .c-tags"):
        tag.decompose()

    parts = []
    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""
    if title:
        parts.append(title)

    sub_el = soup.select_one("h2.c-news__subtitle, .c-news__subtitle")
    if sub_el:
        parts.append(sub_el.get_text(strip=True))

    author_el = soup.select_one(".c-news__author, .c-signature__author")
    if author_el:
        parts.append(author_el.get_text(strip=True))

    date_str = ""
    date_el = soup.select_one("time")
    if date_el:
        date_str = date_el.get_text(strip=True)
        parts.append(date_str)
    parts.append("")

    skip = ["Carregando", "FolhaJus", "Dicas do Editor", "benefício do assinante",
            "assine ou faça login", "ASSINE A FOLHA", "Copiar link", "Salvar para ler",
            "Recurso exclusivo", "Receba no seu email", "A newsletter sobre"]

    body_el = soup.select_one("div.c-news__body, div.c-news__content, article")
    if body_el:
        for p in body_el.find_all(["p", "h2", "h3", "h4"]):
            t = p.get_text(strip=True)
            if len(t) < 10 or any(s in t for s in skip):
                continue
            if t.startswith("https://fotografia.folha"):
                continue
            parts.append(f"\n{t}\n" if p.name in ("h2", "h3", "h4") else t)
    else:
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = True
        h.ignore_images = True
        parts.append(h.handle(html))

    return "\n\n".join(parts).strip(), title, date_str


def _parse_folha_date(s: str) -> str:
    """Folha date strings like '12.mar.2024' → '2024-03'."""
    if not s:
        return ""
    m = re.search(r"(\d{1,2})\.(\w+)\.(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}"
    return ""
