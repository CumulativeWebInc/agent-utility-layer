# human_notify (provisional name)

Push a notification to a human via the configured notification webhook.

Pillar: human · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.010 (human-in-the-loop modules price the approval push at $0.01/exec (venture model default) instead of the $0.001 machine default.)

## Permissions required

- `human:notify`

## Provider setup

Generic webhook POST via stdlib urllib; credentials from ctx.auth_get('notify') as JSON {webhook_url}.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL webhook call — requires credentials + human approval (the approval IS the human loop). Channel is a routing hint for your endpoint. No credentials -> AuthMissing. Demo mode fakes the HTTP layer, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
