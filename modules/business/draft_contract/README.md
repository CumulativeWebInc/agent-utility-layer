# draft_contract (provisional name)

One-line purpose: draft a contract document from a template (mutual NDA,
services agreement, freelance work order) with real field merging.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (document generation only)

## Permissions required

- `contracts:write`

## Provider setup

None. Pure generator — templates live in `handler.py` with declared required
fields; caller-supplied fields are merged locally. No legal database, no
e-sign provider.

## Honest limits

- **Real:** genuine field merging — every required placeholder is verified
  present and non-blank before rendering; missing fields raise an error that
  names exactly what's missing; no unrendered `{placeholders}` leak into
  output (asserted in tests).
- **Not real / stubbed:** this is a TEMPLATE DRAFT, not legal advice and not
  a reviewed contract. It collects no signatures (see `esign_request` for
  signature requests, which stay pending until a human signs). Have an
  attorney review before use. Demo output is the real merged document, not a
  simulated provider.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
