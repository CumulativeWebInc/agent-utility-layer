# issue_refund (provisional name)

Refund a prior charge — full or partial — through a configured payment
provider. **This is a high-stakes module: a human approval is required before
every refund, no exceptions.** No provider credential → `AuthMissing` with
setup instructions. The module never fabricates a refund or settlement.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.05**
- Human-approval push: **$0.01** (standard venture rate)

Why above the $0.001 default: refunds move money in reverse — every execution
carries a mandatory human approval gate, an audit log entry, and settlement
liability. A flat subscription tier ($10–$100/mo per the venture model) would
replace per-exec billing; **tier pricing is Black's call** and is not set here.

## Permissions

`money:refund`

## Provider setup

- **stripe (live):** store your Stripe secret key as provider `stripe` via the
  spine auth flow. Omit `amount_cents` for a full refund; pass it for a
  partial refund.
- **test (simulator):** labeled simulated results (`"simulated": true`) for
  tests and the spine demo page.

## Honest limits

- Only Stripe is implemented as a live provider. Others are unbuilt.
- The handler does not verify the original charge exists before calling the
  provider — Stripe returns the authoritative answer, which is surfaced.
- A refund issued here still requires the human approval that fired before it.

## Kill rule

No real (non-simulated) usage within 60 days of listing → kill the module or
merge it into a sibling.

© 2026 Cumulative Web Inc
