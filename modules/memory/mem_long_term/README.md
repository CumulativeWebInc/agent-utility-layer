# mem_long_term (provisional)

Durable namespaced memory with importance scoring and tags. The persistent fact store memory_sync composes.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:long_term`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real durable sqlite store. Recall is exact-key; query filters by tag/importance only — semantic recall is vector_search's job, not this module's.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
