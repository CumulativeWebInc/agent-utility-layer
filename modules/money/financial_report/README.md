# financial_report (provisional name)

Build a financial summary report (HTML) from the money-module ledgers —
invoices persisted by `create_invoice` and expenses persisted by
`track_expense`. **Read-only aggregation — no credential, no approval, no
money movement.** An empty ledger produces an honest zero report, not an
error.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.01**

$0.01 covers aggregation + HTML rendering. No approval push is billed (no
funds move). A flat subscription tier ($10–$100/mo per the venture model)
would replace per-exec billing; **tier pricing is Black's call** and is not
set here.

## Permissions

`money:report`

## Provider setup

None. Reads `ctx.memory` keys `invoices` and `expenses` written by the
sibling modules.

## Honest limits

- "Invoiced" means issued invoices, **not collected cash** — the report says
  this on the page. Pair with `charge_payment` settlement data for cash truth.
- Multi-currency ledgers report "MIXED" unless you pass `currency` to filter.
  No FX conversion is performed.
- This is a summary document, not audited financial statements. It is not a
  substitute for your accountant.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling.

© 2026 Cumulative Web Inc
