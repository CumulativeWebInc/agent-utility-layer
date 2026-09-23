# calc_tax (provisional name)

Compute tax on an amount for a jurisdiction. **Pure computation — no
credential, no approval, no provider.** Rates come from a small built-in
table of point-in-time **estimates** (2026-09); pass `tax_rate` to override,
or use jurisdiction `CUSTOM` with your own rate.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.01**

$0.01 covers the computation + audit log. No approval push is billed (no
funds move). A flat subscription tier ($10–$100/mo per the venture model)
would replace per-exec billing; **tier pricing is Black's call** and is not
set here.

## Permissions

`money:tax`

## Provider setup

None.

## Honest limits

- **This is not tax advice.** Rates are estimates; local add-ons, product
  categories, exemptions, and rate changes are not modeled. Confirm with a
  tax professional before filing or invoicing.
- Only 10 jurisdictions are tabulated (US-NY, US-CA, US-TX, US-FL, US-WA, GB,
  DE, FR, CA, AU). Everything else goes through `CUSTOM` + explicit rate.
- Currency-agnostic: the module computes on minor units; it does not know
  your currency's rounding rules beyond half-up to the minor unit.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling.

© 2026 Cumulative Web Inc
