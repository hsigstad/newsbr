"""newsbr command-line interface.

Subcommands:
    collect       — search outlets for a query, fetch + append new articles
    fetch         — fetch one or more URLs directly (auto-detects outlet)
    refetch-texts — re-download missing texts/NNN.txt from existing CSV rows
    outlets       — list configured outlets and their status
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from newsbr import outlets as outlet_registry
from newsbr.http import make_session, html_to_text
from newsbr.schema import Article
from newsbr.search_log import OutletResult, SearchLog, SearchRun
from newsbr.store import NewsStore

DEFAULT_DELAY = 1.5


def _add_common(p):
    p.add_argument("--project", required=True, type=Path,
                   help="Project root (the dir containing references/news/)")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                   help="Delay between fetches in seconds")


def cmd_collect(args):
    store = NewsStore(args.project)
    store.ensure()
    log = SearchLog(args.project)

    selected = args.outlets.split(",") if args.outlets else outlet_registry.OUTLET_NAMES
    modules = [outlet_registry.get(n) for n in selected]
    modules = [m for m in modules if m and getattr(m, "STATUS", "working") != "disabled"]

    print(f"Project: {args.project}")
    print(f"Query  : {args.query}")
    print(f"Outlets: {', '.join(getattr(m, 'NAME', '?') for m in modules)}\n")

    existing = store.existing_urls()
    run = SearchRun(query=args.query, project_context=args.context or "")

    for mod in modules:
        name = getattr(mod, "NAME", mod.__name__)
        result = OutletResult(outlet=name, pages=args.max_pages)
        print(f"=== {name} ===")
        try:
            stubs = mod.search(args.query, max_pages=args.max_pages)
        except Exception as e:
            print(f"  search failed: {e}")
            result.note = f"search failed: {e}"
            run.outlets.append(result)
            continue
        result.hits = len(stubs)
        new_stubs = [s for s in stubs if s.url not in existing]
        result.new = len(new_stubs)
        print(f"  {len(stubs)} hits, {len(new_stubs)} new")

        if args.dry_run:
            for s in new_stubs:
                print(f"   - {s.date or '?':10s} {s.title[:80]}")
            run.outlets.append(result)
            continue

        for stub in new_stubs:
            try:
                article = mod.fetch(stub.url)
            except Exception as e:
                print(f"   FAIL {stub.url[:70]}: {e}")
                continue
            if article is None:
                print(f"   SKIP {stub.url[:70]}")
                continue
            if not article.title and stub.title:
                article.title = stub.title
            if not article.date and stub.date:
                article.date = stub.date

            row = store.append(article)
            if row is not None:
                existing.add(article.url)
                result.added += 1
                print(f"   [{row:03d}] OK {article.title[:60]} ({len(article.text):,} chars)")
            time.sleep(args.delay)

        run.outlets.append(result)

    log.append(run)
    total_added = sum(o.added for o in run.outlets)
    print(f"\nDone. {total_added} articles added. Log: {log.path}")


def cmd_fetch(args):
    store = NewsStore(args.project)
    store.ensure()

    urls: list[str] = []
    if args.url:
        urls.extend(args.url)
    if args.file:
        urls.extend(
            u.strip() for u in Path(args.file).read_text().splitlines()
            if u.strip() and not u.startswith("#")
        )
    if not urls:
        print("No URLs provided. Use --url or --file.")
        sys.exit(1)

    existing = store.existing_urls()
    added = 0
    for url in urls:
        url = url.strip().rstrip("/")
        if url in existing:
            print(f"  HAVE  {url[:80]}")
            continue
        mod = _resolve_outlet(url, args.outlet)
        if mod is None:
            article = _generic_fetch(url)
        else:
            try:
                article = mod.fetch(url)
            except Exception as e:
                print(f"  FAIL  {url[:80]}: {e}")
                continue
        if article is None:
            print(f"  SKIP  {url[:80]}")
            continue
        row = store.append(article)
        if row is not None:
            existing.add(url)
            added += 1
            print(f"  [{row:03d}] OK {article.title[:60]}")
        time.sleep(args.delay)

    print(f"\nDone. {added} articles added.")


def cmd_refetch_texts(args):
    """Re-download missing texts/NNN.txt files from existing CSV rows."""
    store = NewsStore(args.project)
    store.ensure()

    fetched = 0
    skipped = 0
    failed = 0
    for row_num, article in store.iter_rows():
        if article.paywalled == "yes":
            skipped += 1
            continue
        out = store.text_path(row_num)
        if out.exists() and not args.overwrite:
            skipped += 1
            continue
        if not article.url:
            failed += 1
            continue
        mod = _resolve_outlet(article.url, None)
        try:
            new_article = mod.fetch(article.url) if mod else _generic_fetch(article.url)
        except Exception as e:
            print(f"  [{row_num:03d}] FAIL {e}")
            failed += 1
            continue
        if new_article and new_article.text:
            out.write_text(new_article.text, encoding="utf-8")
            fetched += 1
            print(f"  [{row_num:03d}] OK {article.title[:60]}")
        else:
            failed += 1
            print(f"  [{row_num:03d}] SKIP")
        time.sleep(args.delay)

    print(f"\nDone. {fetched} fetched, {skipped} skipped, {failed} failed.")


def cmd_outlets(args):
    rows = outlet_registry.list_status()
    print(f"{'name':<20s} {'status':<14s} {'search':<14s}")
    print("-" * 50)
    for r in rows:
        print(f"{r['name']:<20s} {r['status']:<14s} {r['search']:<14s}")


def _resolve_outlet(url: str, hint: Optional[str]):
    if hint:
        return outlet_registry.get(hint)
    host = urlparse(url).netloc.lower()
    for name in outlet_registry.OUTLET_NAMES:
        mod = outlet_registry.get(name)
        if mod and getattr(mod, "DOMAIN", "") in host:
            return mod
    return None


def _generic_fetch(url: str) -> Optional[Article]:
    """Best-effort fetch for outlets without a dedicated module."""
    try:
        resp = make_session().get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None
    text = html_to_text(resp.text)
    if len(text) < 200:
        return None
    host = urlparse(url).netloc
    return Article(
        url=url, outlet=host, title="",
        summary=text[:300], text=text,
    )


def main():
    p = argparse.ArgumentParser(prog="newsbr", description=__doc__)
    sub = p.add_subparsers(dest="command")

    c = sub.add_parser("collect", help="Search outlets and append new articles")
    _add_common(c)
    c.add_argument("--query", required=True, help="Search query")
    c.add_argument("--outlets", help="Comma-separated outlet names (default: all)")
    c.add_argument("--max-pages", type=int, default=1)
    c.add_argument("--dry-run", action="store_true",
                   help="List candidates without fetching")
    c.add_argument("--context", default="",
                   help="Free-form note for the search log (e.g. project name)")
    c.set_defaults(func=cmd_collect)

    f = sub.add_parser("fetch", help="Fetch specific URLs directly")
    _add_common(f)
    f.add_argument("--url", action="append", help="URL (repeatable)")
    f.add_argument("--file", help="File of URLs, one per line")
    f.add_argument("--outlet", help="Force outlet module (e.g. conjur)")
    f.set_defaults(func=cmd_fetch)

    r = sub.add_parser("refetch-texts", help="Re-fetch missing texts/NNN.txt")
    _add_common(r)
    r.add_argument("--overwrite", action="store_true")
    r.set_defaults(func=cmd_refetch_texts)

    o = sub.add_parser("outlets", help="List configured outlets")
    o.set_defaults(func=cmd_outlets)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
