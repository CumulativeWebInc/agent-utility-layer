# api_call (provisional name)

Call a JSON REST API endpoint with a named credential injected as the Authorization header.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `http:request`
- `vault:read`

## Provider setup
Credential string comes from ctx.auth_get(auth_provider); sent as 'Authorization: Bearer <cred>'. Configure the named credential out-of-band (spine auth) — never in the repo or inputs.

## Approval
Missing credential -> AuthMissing. Non-GET methods require ctx.approval_request.

## Honest limits
- Real HTTPS via urllib. Credential is injected as a Bearer token; providers needing other schemes (HMAC, OAuth1) are not supported in v1 — wrap them with http_request + vault:read.
- Non-JSON responses are returned as raw text in 'data'.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
