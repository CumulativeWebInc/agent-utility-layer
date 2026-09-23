# helpdesk_ticket (provisional name)

One-line purpose: create, track, assign, comment on, and close helpdesk
tickets with real status transitions in a JSON-backed store.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (internal store only)

## Permissions required

- `tickets:write`

## Provider setup

No external provider. Tickets live in the spine's scoped memory
(`ctx.memory`, key `aul:tickets_v1`). A Zendesk/Freshdesk connector would
sit behind `ctx.auth_get('helpdesk')` — not present today.

## Honest limits

- **Real:** full ticket lifecycle — create, update, comment, assign, close,
  reopen (resolved/closed only), list/filter. Timestamps and ids are real.
- **Not real / stubbed:** no sync to any external helpdesk. No SLA engine,
  no email notifications (those would route through `send_email` with an
  approval). Demo runs against an in-memory FakeCtx, labeled
  "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
