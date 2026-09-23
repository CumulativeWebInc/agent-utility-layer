# http_request (provisional name)

Make a real HTTP(S) request with urllib (GET/POST/PUT/PATCH/DELETE/HEAD).

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `http:request`

## Provider setup
No provider or credential needed; pure urllib stdlib request.

## Approval
Write methods (POST/PUT/PATCH/DELETE) require ctx.approval_request (destructive/external). GET/HEAD do not.

## Honest limits
- Real HTTP via stdlib urllib only.
- No JavaScript rendering — static responses only.
- Only http/https schemes; redirects followed up to 5 hops.
- Response bodies truncated at max_response_bytes (flagged).

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
