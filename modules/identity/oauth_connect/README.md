# oauth_connect (provisional name)

OAuth2 flow scaffolding: build a standards-compliant authorization URL, and exchange a code for tokens.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `identity:oauth`
- `http:send`

## Provider setup
Bring your provider credentials: client_secret comes from ctx.auth_get(secret_provider) at exchange time. Provider endpoints are passed in (authorization_endpoint/token_endpoint) so any RFC 6749 provider works — nothing is hardcoded.

## Approval
exchange_code requires ctx.approval_request (external token exchange). build_auth_url does not. Missing secret -> AuthMissing.

## Honest limits
- The browser redirect itself is outside this module — build_auth_url returns the URL for the agent/human to visit; the returned 'code' is exchanged via exchange_code.
- Tokens are returned in the output — treat them as secrets; the handler never logs them.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
