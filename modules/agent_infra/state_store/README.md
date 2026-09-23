# state_store (provisional)

Namespaced key-value store with TTL and compare-and-set for optimistic concurrency.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:state_store`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real namespaced KV with TTL (lazy expiry) and CAS versioning. Optimistic concurrency only — no transactions exposed across keys.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
