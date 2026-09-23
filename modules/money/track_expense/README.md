# track_expense (provisional name)

Record, list, and summarize business expenses. **Internal bookkeeping only —
this module moves no money.** Expenses are stored in the module's scoped
memory, fully reversible, and read by `financial_report` for P&L-style
summaries. No credential and no approval are needed.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.01**

$0.01 covers ledger writes/reads. No approval push is billed (no funds move).
A flat subscription tier ($10–$100/mo per the venture model) would replace
per-exec billing; **tier pricing is Black's call** and is not set here.

## Permissions

`money:expense`

## Provider setup

None.

## Honest limits

- This is a scoped ledger, not your accounting system — no QuickBooks/Xero
  sync, no bank import, no receipt OCR. Export is unbuilt.
- Multi-currency expenses are stored as-is; summaries do not convert
  currencies. Convert before recording for single-currency reports.
- Scoped to the calling agent's module memory unless the spine shares it.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling.

© 2026 Cumulative Web Inc
