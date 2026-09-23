# error_recovery (provisional)

Recovery playbook registry: register playbooks per error class, get regex-matched recovery suggestions.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `agent:error_recovery`

## Provider setup
sqlite3 via stdlib; regex matching via stdlib re.

## Honest limits
Real playbook storage and regex matching. Suggestions are advisory text — the module does not execute recovery steps itself.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
