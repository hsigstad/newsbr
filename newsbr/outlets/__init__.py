"""Outlet registry. Each outlet module exposes:

    NAME: str           # display name (e.g. "Conjur")
    DOMAIN: str         # primary domain for site: queries
    STATUS: str         # "working" | "rss_only" | "disabled"
    SEARCH: str         # "native" | "google_news" | "sitemap"

    def search(query: str, max_pages: int = 1) -> list[Article]:
        '''Discover articles. Stub Articles (url+title+date) are OK.'''

    def fetch(url: str) -> Article | None:
        '''Full fetch — returns Article with text populated, or None on failure.'''
"""

from importlib import import_module
from typing import Optional

# Order matters for default --outlets list
OUTLET_NAMES = ["conjur", "migalhas", "estadao", "globo", "folha", "piaui"]


def get(name: str):
    """Import an outlet module by short name. Returns None if not found."""
    name = name.lower().strip()
    if name not in OUTLET_NAMES:
        return None
    try:
        return import_module(f"newsbr.outlets.{name}")
    except ImportError:
        return None


def all_outlets() -> list:
    """Return all importable outlet modules whose STATUS is not 'disabled'."""
    out = []
    for name in OUTLET_NAMES:
        mod = get(name)
        if mod and getattr(mod, "STATUS", "working") != "disabled":
            out.append(mod)
    return out


def list_status() -> list[dict]:
    """Return [{name, status, search}] for all outlets, including unimportable ones."""
    rows = []
    for name in OUTLET_NAMES:
        mod = get(name)
        if mod is None:
            rows.append({"name": name, "status": "import_error", "search": "?"})
        else:
            rows.append({
                "name": getattr(mod, "NAME", name),
                "status": getattr(mod, "STATUS", "working"),
                "search": getattr(mod, "SEARCH", "google_news"),
            })
    return rows
