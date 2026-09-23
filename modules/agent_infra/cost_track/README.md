# cost_track (provisional)

Spend ledger per agent/capability: record micro-costs, aggregate totals. Feeds spine billing.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `billing:cost_track`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real spend aggregation in USD. No currency conversion, no tax handling. Recording a cost here does not charge anyone — it feeds the spine billing ledger, which owns settlement.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
