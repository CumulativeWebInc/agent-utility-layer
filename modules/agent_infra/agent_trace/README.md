# agent_trace (provisional)

Distributed-trace style span store: start/end spans, assemble trace trees.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:trace`

## Provider setup
sqlite3 via stdlib; tree assembly in pure Python.

## Honest limits
Real span storage and tree assembly. No sampling and no automatic instrumentation — spans are created by explicit calls.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
