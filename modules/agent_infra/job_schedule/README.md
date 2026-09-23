# job_schedule (provisional)

Schedule definitions (cron or interval) with real due-job computation. Execution hooks to the spine.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:job_schedule`

## Provider setup
sqlite3 via stdlib; 5-field cron parser in pure Python.

## Honest limits
Real cron/interval parsing and due computation. This module never executes jobs — the spine polls `due` and dispatches. Cron supports *, */n, lists, ranges (no named months/days). Times are UTC epoch seconds.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
