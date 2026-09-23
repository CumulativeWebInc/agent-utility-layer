# create_invoice (provisional name)

Generate a real invoice document (HTML) with line items, tax, and totals.
**This module creates a document — it moves no money.** No human approval and
no provider credential are needed. Issued invoices are persisted in the
module's scoped memory so `financial_report` can aggregate them.

## Pricing

- Setup: **$1.00**
- Per execution: **$0.01**

$0.01 covers document rendering + ledger persistence. No approval push is
billed (no funds move). A flat subscription tier ($10–$100/mo per the venture
model) would replace per-exec billing; **tier pricing is Black's call** and is
not set here.

## Permissions

`money:invoice`

## Provider setup

None. The module is provider-free: totals use `Decimal` half-up rounding, HTML
is rendered locally, invoices persist via `ctx.memory`.

## Honest limits

- Output is an HTML invoice document. PDF generation is not built — print the
  HTML to PDF from a browser, or request a pdf module.
- Tax is a flat rate you pass in; use `calc_tax` for jurisdiction tables.
- Persistence is scoped module memory (spine-backed), not your accounting
  system. Export to QuickBooks/Xero is unbuilt.
- Invoices are drafts-by-construction: issuing an invoice is not a charge —
  collect payment with `charge_payment`.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling.

© 2026 Cumulative Web Inc
