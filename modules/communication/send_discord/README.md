# send_discord (provisional name)

Post a message to a Discord channel via incoming webhook.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `discord:post`

## Provider setup

Discord webhook POST via stdlib urllib (?wait=true to capture the message id); credentials from ctx.auth_get('discord') as JSON {webhook_url}.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL Discord webhook call — requires credentials + human approval. No credentials -> AuthMissing. Demo mode fakes the HTTP layer, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
