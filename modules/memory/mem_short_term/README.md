# mem_short_term (provisional)

Ephemeral per-session key-value memory with TTL. Backs working memory for a single agent session.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:short_term`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real sqlite persistence with TTL enforced lazily on read (expired keys are purged when read/listed). Single-machine store, not a distributed cache. TTL is best-effort wall-clock.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
