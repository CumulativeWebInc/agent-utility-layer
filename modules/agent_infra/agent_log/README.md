# agent_log (provisional)

Structured JSONL event log for agents: write entries, query by agent/level/event/time.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:log`

## Provider setup
JSONL file via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real append-only JSONL logging with query by scan. No log rotation built in — rotate the file externally. Queries scan the file; fine for operational volumes.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
