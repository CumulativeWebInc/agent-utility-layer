# user_profile (provisional)

Per-user profile document store with deep-merge updates and dotted-field reads.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:user_profile`

## Provider setup
sqlite3 via stdlib; store dir from ctx.store_dir, $AUL_STORE_DIR, or ~/.aul/data.

## Honest limits
Real JSON document merge (recursive dict merge; lists replaced). No PII encryption at rest in this module — platform-level encryption applies. No schema enforcement; the profile is schemaless.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
