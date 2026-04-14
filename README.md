# newsbr

Brazilian news collection toolkit. Discover articles from Brazilian outlets
(or fall back to Google News for non-Brazil topics), fetch full text, and
store everything under a project's `references/news/` directory using a
canonical CSV + texts/ layout.

Used by the `/anecdotes` Claude Code skill.

## Layout

For a project at `<project>/`:

```
<project>/references/news/
├── stories.csv          date,outlet,title,url,theme,summary,paywalled
├── texts/NNN.txt        full article text, 1-indexed zero-padded
└── search_log.md        audit trail: query, outlet, hits, kept
```

## CLI

```bash
# Collect from baseline Brazilian outlets
python -m newsbr collect --project /path/to/project --query "venda de sentenças"

# Restrict to specific outlets
python -m newsbr collect --project /path --query "..." --outlets conjur,migalhas

# Fetch specific URLs
python -m newsbr fetch --project /path --url https://...
python -m newsbr fetch --project /path --file urls.txt

# Re-fetch missing article texts from existing stories.csv rows
python -m newsbr refetch-texts --project /path

# List configured outlets and their status
python -m newsbr outlets
```

## Outlets

| Module | Status | Native search | Notes |
|--------|--------|---------------|-------|
| conjur | working | google_news | free; no paywall |
| migalhas | working | google_news | free; no paywall |
| estadao | working | topic+rss | JS-only paywall — full text in initial HTML |
| globo | working | sitemap | requires Chrome cookies (rookiepy) |
| folha | working | search api | requires Chrome cookies (rookiepy) |
| piaui | rss_only | sitemap | playwright-based, Chrome cookies |

Outlets without a dedicated module fall back to Google News RSS with a
`site:` filter.
