"""NewsStore — manages references/news/{stories.csv, texts/} for a project."""

import csv
from pathlib import Path
from typing import Iterable, Optional

from newsbr.schema import Article, CSV_FIELDS


class NewsStore:
    """Read/write the canonical references/news/ layout for one project."""

    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self.dir = self.root / "references" / "news"
        self.csv_path = self.dir / "stories.csv"
        self.texts_dir = self.dir / "texts"

    def ensure(self) -> None:
        """Create dirs and CSV header if missing."""
        self.texts_dir.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(CSV_FIELDS)

    def existing_urls(self) -> set[str]:
        if not self.csv_path.exists():
            return set()
        urls = set()
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                u = row.get("url", "").strip().strip('"')
                if u:
                    urls.add(u)
        return urls

    def has(self, url: str) -> bool:
        return url in self.existing_urls()

    def next_row_num(self) -> int:
        """1-indexed row number for the next article (skipping header)."""
        if not self.csv_path.exists():
            return 1
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = sum(1 for _ in reader)
        # If file has a header row, rows includes it. Next data row = rows.
        return max(rows, 1)

    def text_path(self, row_num: int) -> Path:
        return self.texts_dir / f"{row_num:03d}.txt"

    def append(self, article: Article) -> Optional[int]:
        """Append article to CSV and write text file. Returns row number, or None if duplicate."""
        self.ensure()
        if self.has(article.url):
            return None

        row_num = self.next_row_num()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(article.to_csv_row())

        if article.text:
            self.text_path(row_num).write_text(article.text, encoding="utf-8")
        return row_num

    def append_many(self, articles: Iterable[Article]) -> list[int]:
        """Append multiple articles, deduplicating against existing CSV. Returns row numbers added."""
        added = []
        for a in articles:
            n = self.append(a)
            if n is not None:
                added.append(n)
        return added

    def iter_rows(self) -> Iterable[tuple[int, Article]]:
        """Iterate (row_num, Article) pairs from stories.csv."""
        if not self.csv_path.exists():
            return
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                yield i, Article.from_csv_row(row)
