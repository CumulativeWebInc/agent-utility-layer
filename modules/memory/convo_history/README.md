# convo_history (provisional)

Append-only conversation history per session with paged retrieval.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:convo_history`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real append/query store. Search is substring match, not semantic. No summarization or compaction — a future module can compose over history.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
