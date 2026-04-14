"""Article dataclass — matches the stories.csv schema used across projects."""

from dataclasses import dataclass, field, asdict
from typing import Optional

CSV_FIELDS = ["date", "outlet", "title", "url", "theme", "summary", "paywalled"]


@dataclass
class Article:
    url: str
    outlet: str = ""
    title: str = ""
    date: str = ""           # YYYY-MM-DD or YYYY-MM (partial allowed)
    theme: str = ""          # project-specific tag; left blank for caller to fill
    summary: str = ""        # short blurb (~300 chars)
    paywalled: str = "no"    # "yes" | "no"
    text: str = ""           # full article body — written to texts/NNN.txt, not CSV

    def to_csv_row(self) -> list[str]:
        return [self.date, self.outlet, self.title, self.url,
                self.theme, self.summary, self.paywalled]

    @classmethod
    def from_csv_row(cls, row: dict) -> "Article":
        return cls(
            url=row.get("url", "").strip().strip('"'),
            outlet=row.get("outlet", ""),
            title=row.get("title", ""),
            date=row.get("date", ""),
            theme=row.get("theme", ""),
            summary=row.get("summary", ""),
            paywalled=(row.get("paywalled", "no") or "no").strip().lower(),
        )
