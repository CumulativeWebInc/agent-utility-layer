# human_forms (provisional name)

Build a structured form definition (typed fields) for a human to fill in.

Pillar: human · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `human:forms`

## Provider setup

No external provider. Form spec validated (text/number/boolean/choice/date; choice requires options) and stored via ctx.memory_set.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

Creation only — builds and stores the form spec, returns a preview path. Does NOT send the form to anyone (use human_notify for delivery) and does NOT collect submissions (no submission endpoint yet). No approval required for creation.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
