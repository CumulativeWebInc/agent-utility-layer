# send_whatsapp (provisional name)

Send a WhatsApp message via Twilio's WhatsApp API.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `whatsapp:send`

## Provider setup

Twilio WhatsApp Messages API via stdlib urllib; credentials from ctx.auth_get('twilio') as JSON {account_sid, auth_token, whatsapp_from}.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL Twilio API call — requires credentials + human approval and a WhatsApp-enabled Twilio sender. Twilio charges apply on your Twilio account. No credentials -> AuthMissing. Demo mode fakes the HTTP layer, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge into send_sms.

---
© 2026 Cumulative Web Inc
