# crm_record (provisional name)

One-line purpose: create, read, update, delete, list, and search CRM records
(contacts, companies, deals, leads) in a JSON-backed store.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (no approval path; internal store only)

## Permissions required

- `crm:write`

## Provider setup

No external provider. Records live in the spine's scoped memory
(`ctx.memory`, key `aul:crm_records_v1`). A future Salesforce/HubSpot
connector would be configured via `ctx.auth_get('crm')` — not present today.

## Honest limits

- **Real:** full CRUD + search over records you create through this module;
  ids, timestamps, and search are computed, not fabricated.
- **Not real / stubbed:** there is no sync to any external CRM (Salesforce,
  HubSpot, etc.). Records exist only inside the Agent Utility Layer store.
  The spine demo page runs this module against an in-memory fake ctx and is
  labeled "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
