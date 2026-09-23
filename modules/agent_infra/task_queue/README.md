# task_queue (provisional)

FIFO task queue with lease semantics, priority ordering, retries, and dead-letter.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:task_queue`

## Provider setup
sqlite3 via stdlib; FIFO + lease in SQL.

## Honest limits
Real FIFO with lease (invisible while leased). Single-machine sqlite — safe for one process, not a distributed broker. Expired leases become visible again on the next lease call.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
