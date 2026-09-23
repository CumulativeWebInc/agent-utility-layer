# charge_payment (provisional name)

Charge a customer through a configured payment provider. **This is a
high-stakes module: a human approval is required before every charge, no
exceptions.** No provider credential → `AuthMissing` with setup instructions.
The module never fabricates a charge, settlement, or receipt.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.05**
- Human-approval push: **$0.01** (standard venture rate)

Why above the $0.001 default: money movement is the highest-stakes capability
in the catalog — every execution carries a mandatory human approval gate, an
audit log entry, and real-world settlement liability. The $0.05 per-exec price
reflects approval routing + audit cost, not compute. A flat subscription tier
($10–$100/mo per the venture model) would replace per-exec billing; **tier
pricing is Black's call** and is not set here.

## Permissions

`money:charge`

## Provider setup

- **stripe (live):** store your Stripe secret key as provider `stripe` via the
  spine auth flow (`ctx.auth_get('stripe')`). The handler creates a Stripe
  PaymentIntent with stdlib `urllib` — no third-party dependencies. Test keys
  (sk_test_...) hit Stripe's sandbox; live keys move real money and still
  require human approval first.
- **test (simulator):** `provider="test"` returns a labeled simulated charge
  (`"simulated": true`) for tests and the spine demo page. Simulated results
  are never presented as live charges.

## Honest limits

- Only Stripe is implemented as a live provider. Other processors (PayPal,
  Square, Adyen) are unbuilt, not "coming soon."
- The handler creates the PaymentIntent; capture/confirmation is the
  merchant's Stripe-dashboard or follow-up call, not this module.
- Single-charge cap: 999,999.99 (minor units) — above that, split or use your
  provider dashboard.
- Currency is any 3-letter ISO code; your provider account must support it.

## Kill rule

No real (non-simulated) usage within 60 days of listing → kill the module or
merge it into a sibling.

© 2026 Cumulative Web Inc
