# approval_request (provisional name)

One-line purpose: pause agent execution and issue a signed 1-tap human
confirmation link — `POST /v1/approval/request` from the concept doc.

## Pricing

- Setup: $1.00
- Per execution: **$0.01** (the venture model's human-approval push price)
- Human-approval push: this IS the approval module — the $0.01 is its exec price

## Permissions required

- `human:approval`

## Provider setup

- Signing key: `ctx.auth_get('approval_signing_key')`. If unconfigured, the
  module generates an ephemeral per-machine key (stored in `ctx.memory` under
  `aul:approval_signing_key_v1`) and **honestly labels** the record
  `signature_mode: "local_ephemeral"` — verifiable by this machine only.
- Channel dispatch (`sms`/`whatsapp`/`push`): real sends are the job of Crew C's
  `send_*` modules behind the credential `{channel}_send`. This module never
  claims a message was sent: delivery is `not_attempted` (no credential) or
  `queued_locally` (credential present; actual dispatch by the provider
  integration).

Setup instructions when a send provider is missing: configure the channel
credential for the corresponding Crew C send module (it will raise
`AuthMissing` with its own setup instructions) — the approval record stays
pending and the 1-tap URL remains the lookup key.

## Honest limits

- **Real:** HMAC-SHA256 signed pending records persisted via `ctx.memory`;
  tamper detection via `verify_signature`; real expiry timestamps; unique
  `request_id` per request.
- **Not real / stubbed:** the `approval_url` is a placeholder — the
  human-facing endpoint is provisioned at deploy time. No SMS/WhatsApp/push
  message is sent by this module, ever; delivery states say so explicitly.
  Demo runs against an in-memory FakeCtx, labeled "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling human_loop module.

© 2026 Cumulative Web Inc
