# web_search (provisional name)

Run a web search through a configured provider and return ranked results.
Never fabricates results: with no provider key it raises AuthMissing, not invented hits.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.005 (above the $0.001 default — passes through provider API cost and billed search units) |
| Human approval | n/a (read-only; no approval gate) |

## Permissions

- `net:egress:search`

## Provider setup

Supported providers: `tavily`, `serper`, `brave`. Store the provider's API key
under the provider name via the spine credential flow (never in the repo):

- **tavily** — free key at https://tavily.com (1,000 searches/mo free)
- **serper** — key at https://serper.dev (2,500 searches/mo free)
- **brave** — key at https://brave.com/search/api/

Without a key, `execute` raises `AuthMissing` with these instructions.

## Inputs

- `query` (required) — search text
- `provider` — `tavily` (default), `serper`, `brave`
- `max_results` — 1..50, default 10
- `site` — optional `site:` scoping, e.g. `"example.com"`
- `exclude` — optional list of terms to exclude (`-term`)
- `timeout_seconds` — default 20

## Honest limits

- Real live provider calls over HTTPS via stdlib `urllib`. No bundled fake corpus.
- Query builder does `site:` scoping and `-term` exclusions; it does no
  ranking, dedup, or freshness filtering beyond what the provider returns.
- Results are only as fresh/complete as the provider's index. A zero-result
  response is reported as zero, never padded.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
