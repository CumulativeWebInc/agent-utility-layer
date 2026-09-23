# send_push (provisional name)

Deliver a push notification through a generic provider HTTP hook.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `push:send`

## Provider setup

Generic provider POST via stdlib urllib; credentials from ctx.auth_get('push') as JSON {endpoint_url, api_key, auth_scheme}. Map to FCM / OneSignal / ntfy by setting endpoint_url.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

Provider-agnostic hook: real delivery depends on the endpoint you configure. Requires credentials + human approval. No credentials -> AuthMissing. Demo mode fakes the HTTP layer, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
