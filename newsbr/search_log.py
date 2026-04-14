"""SearchLog — append-only audit trail for newsbr collection runs.

Writes to <project>/references/news/search_log.md so future readers (and
paper reviewers) can see exactly which queries produced which evidence.
"""

from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class OutletResult:
    outlet: str
    pages: int = 0
    hits: int = 0       # URLs returned by search
    new: int = 0        # not already in stories.csv
    added: int = 0      # successfully fetched and appended
    note: str = ""


@dataclass
class SearchRun:
    query: str
    outlets: list[OutletResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    project_context: str = ""   # e.g. project name, where query came from


class SearchLog:
    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self.path = self.root / "references" / "news" / "search_log.md"

    def append(self, run: SearchRun) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ts = run.timestamp.strftime("%Y-%m-%d %H:%M")
        lines = [f"## {ts} — query: {run.query!r}"]
        if run.project_context:
            lines.append(f"- _context: {run.project_context}_")
        total_added = 0
        for o in run.outlets:
            lines.append(
                f"- **{o.outlet}**: {o.hits} hits, {o.new} new, "
                f"{o.added} added (pages: {o.pages})"
                + (f" — {o.note}" if o.note else "")
            )
            total_added += o.added
        lines.append(f"- **total added: {total_added}**")
        lines.append("")

        with open(self.path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
