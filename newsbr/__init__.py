"""newsbr — Brazilian news collection toolkit."""

from newsbr.schema import Article
from newsbr.store import NewsStore
from newsbr.search_log import SearchLog

__all__ = ["Article", "NewsStore", "SearchLog"]
__version__ = "0.1.0"
