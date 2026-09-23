# agent_analytics (provisional)

Aggregations over the agent event log: counts by level/event, error rates, top events.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:analytics`

## Provider setup
Reads the agent_log JSONL store; pure-Python aggregation.

## Honest limits
Real aggregations computed by scanning the JSONL log — honest counts, no sampling. Requires agent_log data to exist; empty log yields zeros (reported as zeros, not hidden).

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
