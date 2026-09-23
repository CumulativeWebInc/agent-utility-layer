# send_slack (provisional name)

Post a message to Slack via incoming webhook or bot token.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `slack:post`

## Provider setup

Slack incoming webhook or chat.postMessage via stdlib urllib; credentials from ctx.auth_get('slack') as JSON {webhook_url} or {bot_token}.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL Slack API call — requires credentials + human approval. Webhook mode returns ts='webhook' (Slack webhooks return no timestamp). No credentials -> AuthMissing. Demo mode fakes the HTTP layer, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
