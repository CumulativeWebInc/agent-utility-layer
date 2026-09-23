# site_monitor (provisional name)

Single uptime check of a URL (status + optional text match) with state-change detection across runs.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `http:request`

## Provider setup
No provider needed. Previous state is kept in ctx.memory (scoped KV).

## Approval
None required.

## Honest limits
- One check per execution — this is NOT a scheduler. Pair with Crew H job_schedule for intervals.
- State lives in ctx.memory; a fresh/empty store reports state_changed=false on first check.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
