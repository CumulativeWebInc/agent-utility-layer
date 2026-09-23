# web_scrape (provisional name)

Fetch a public web page over HTTP(S) and extract readable text, the page
title, and links. Real fetching via stdlib `urllib` + `html.parser`.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.005 (above the $0.001 default — outbound bandwidth + target-site load) |
| Human approval | n/a (read-only fetch) |

## Permissions

- `net:egress:http`

## Inputs

- `url` (required) — absolute `http(s)` URL only
- `extract_mode` — `text` (default), `html`, `links`
- `timeout_seconds` — default 20
- `max_bytes` — default 1 MiB; larger bodies are cut and flagged `truncated`
- `user_agent` — default `CWI-AgentUtilityLayer/1.0`

## Honest limits

- No JavaScript rendering: pages that require JS to render content return the
  raw HTML shell. Use a browser-automation path for those (not this module).
- Readability is heuristic (skips `script`/`style`/`noscript`); complex layouts
  may interleave text imperfectly. Raw HTML is returned in `html` mode for
  exactness.
- Only `http`/`https` URLs. No login-gated pages (no cookie/session support).
- Respects robots.txt only manually — the module fetches exactly what it is
  told to fetch, so callers must check site policy themselves.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
