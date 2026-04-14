"""Shared HTTP helpers: session factory, headers, html2text converter."""

import html2text
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = 30


def make_session(headers: dict | None = None, retries: int = 3) -> requests.Session:
    """Create a requests session with retries and standard headers."""
    s = requests.Session()
    s.headers.update(headers or DEFAULT_HEADERS)
    retry = Retry(
        total=retries,
        backoff_factor=1.0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def make_chrome_session(domains: list[str]) -> requests.Session:
    """Session with Chrome cookies for given domains. Requires rookiepy."""
    try:
        import rookiepy
    except ImportError as e:
        raise RuntimeError(
            "rookiepy is required for Chrome-cookie sessions. "
            "Install with: pip install 'newsbr[cookies]'"
        ) from e
    cookies = rookiepy.chrome(domains=domains)
    s = make_session()
    for c in cookies:
        s.cookies.set(
            c["name"], c["value"],
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
        )
    return s


def make_converter() -> html2text.HTML2Text:
    h = html2text.HTML2Text()
    h.body_width = 0
    h.ignore_links = True
    h.ignore_images = True
    h.ignore_emphasis = False
    h.skip_internal_links = True
    return h


def html_to_text(html: str) -> str:
    return make_converter().handle(html).strip()
