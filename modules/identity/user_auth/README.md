# user_auth (provisional name)

Register and verify user credentials (PBKDF2-hashed) against the scoped credential store.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `identity:auth`

## Provider setup
No external provider. Credentials are stored as PBKDF2-HMAC-SHA256 hashes (200k rounds, per-user salt) in ctx.memory — the spine persists that store; plaintext is never stored.

## Approval
register requires ctx.approval_request (creates an identity record). verify/rotate do not.

## Honest limits
- Password rules enforced: >=12 chars. Timing-safe comparison on verify.
- This is application-level auth, not the spine's API-key auth (spine/auth.py) — no overlap.
- Session/token issuance is NOT in v1 — verify returns ok:true only.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
