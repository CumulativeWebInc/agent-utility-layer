# browser_action (provisional name)

Submit a plain-HTML form on a page (fetch, parse, POST) — the v1 honest stand-in for browser automation.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `http:send`

## Provider setup
No provider needed.

## Approval
Always requires ctx.approval_request (external send / side effects).

## Honest limits
- NOT a real browser. No JavaScript, no cookies/session beyond one request, no CAPTCHA solving, no login flows that need JS. Works only with plain HTML forms.
- Form identified by index (form.index) or name (form.name); unknown fields raise ModuleError.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
