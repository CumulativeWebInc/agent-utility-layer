# retry_policy (provisional)

Retry math (linear/exponential backoff + jitter) plus a dead-letter store for exhausted operations.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:retry_policy`

## Provider setup
Pure-Python backoff math; dead-letter in sqlite.

## Honest limits
Real backoff computation, but this module does NOT sleep or retry anything itself — the caller executes retries using the computed delays. Dead-letter is a real persistent store.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
