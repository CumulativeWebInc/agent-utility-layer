# manage_subscription (provisional name)

Create, update, cancel, or inspect a subscription on a configured payment
provider. **State-changing actions (create, update, cancel) require human
approval first — no exceptions.** The read-only `get` action needs no
approval. No provider credential → `AuthMissing` with setup instructions.
Never fabricates subscription state.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.05**
- Human-approval push: **$0.01** (standard venture rate, only for
  state-changing actions)

Why above the $0.001 default: subscription changes move recurring money —
each one carries a mandatory approval gate, an audit log entry, and
recurring-revenue liability. A flat subscription tier ($10–$100/mo per the
venture model) would replace per-exec billing; **tier pricing is Black's
call** and is not set here.

## Permissions

`money:subscription`

## Provider setup

- **stripe (live):** store your Stripe secret key as provider `stripe` via the
  spine auth flow. Create takes a Stripe Price id (`price_...`); cancel
  deletes the subscription immediately (use `update` with
  `cancel_at_period_end: true` to cancel at the billing boundary).
- **test (simulator):** labeled simulated results (`"simulated": true`) for
  tests and the spine demo page.

## Honest limits

- Only Stripe is implemented as a live provider. Others are unbuilt.
- `get` reads live provider state — it is not cached.
- Trial, proration, and coupon behavior follows Stripe defaults; the module
  does not model them.

## Kill rule

No real (non-simulated) usage within 60 days of listing → kill the module or
merge it into a sibling.

© 2026 Cumulative Web Inc
