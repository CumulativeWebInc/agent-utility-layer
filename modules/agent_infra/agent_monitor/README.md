# agent_monitor (provisional)

Agent heartbeat registry with staleness detection.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:monitor`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real heartbeat tracking; staleness is computed at query time against wall clock. No push alerting — consumers poll status/list.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
