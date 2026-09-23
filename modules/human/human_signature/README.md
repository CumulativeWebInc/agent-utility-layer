# human_signature (provisional name)

Send a signature REQUEST to a human signer via email (request only, not e-sign).

Pillar: human · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.010 (human-in-the-loop modules price the approval push at $0.01/exec (venture model default) instead of the $0.001 machine default.)

## Permissions required

- `human:signature`
- `email:send`

## Provider setup

Email request via SMTP (ctx.auth_get('smtp')); request recorded via ctx.memory_set.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

HONEST SCOPE: sends an email ASKING the human to sign and records the request. This is NOT a legal e-signature provider — no DocuSign/Adobe Sign integration, no audit-trail certificate. Requires SMTP credentials + human approval.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
