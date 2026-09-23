# page_interact (provisional name)

Fetch a page and extract structured content (title, headings, links, forms, meta, text) with stdlib HTML parsing.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `http:request`

## Provider setup
No provider needed.

## Approval
None required.

## Honest limits
- Static HTML only — NO JavaScript execution. SPA/React pages return their shell markup, honestly labeled.
- Forms are extracted (action, method, fields) but NOT submitted — use browser_action for submission.
- Non-HTML content raises ModuleError rather than returning garbage.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
