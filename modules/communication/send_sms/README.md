# send_sms (provisional name)

Send an SMS text message via Twilio's REST API.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `sms:send`

## Provider setup

Twilio Messages API via stdlib urllib; credentials from ctx.auth_get('twilio') as JSON {account_sid, auth_token, from_number}.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL Twilio API call — requires credentials + human approval. Twilio usage itself bills to your Twilio account (outside this ledger). No credentials -> AuthMissing. Demo mode fakes the HTTP layer, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge into send_whatsapp.

---
© 2026 Cumulative Web Inc
