# webhook_emit (provisional name)

Emit a signed JSON webhook POST to a target URL (HMAC-SHA256 signature header when configured).

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `http:send`

## Provider setup
Signing secret (if sign=true) from ctx.auth_get(secret_provider), sent as X-Webhook-Signature (sha256=<hex>). Without a secret the POST is sent unsigned.

## Approval
Always requires ctx.approval_request (external send). Human denial -> ApprovalDenied, nothing sent.

## Honest limits
- Real POST via urllib. At-least-once delivery semantics are NOT guaranteed in v1 — no retry queue, no dead-letter; retries are the caller's job (see Crew H retry_policy).
- Signature uses HMAC-SHA256 over the raw JSON body.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
