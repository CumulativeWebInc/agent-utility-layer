# gl_entry (provisional name)

One-line purpose: post balanced double-entry journal entries, void entries,
and compute a trial balance on a JSON-backed ledger.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (internal store only)

## Permissions required

- `ledger:write`

## Provider setup

No external provider. The journal lives in the spine's scoped memory
(`ctx.memory`, key `aul:gl_journal_v1`). No bank or accounting-software
integration.

## Honest limits

- **Real:** genuine double-entry enforcement — debits must equal credits per
  entry or the post is rejected and nothing is written; per-account trial
  balance computed with exact decimal arithmetic; voiding keeps the audit
  trail (entries are never deleted).
- **Not real / stubbed:** this is bookkeeping, not GAAP-certified accounting
  software and not a bank connection. Have an accountant review anything that
  feeds tax filings. Demo runs against an in-memory FakeCtx, labeled
  "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
