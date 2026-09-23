# human_escalate (provisional name)

Escalate an issue to a human owner with a priority level (recorded internally).

Pillar: human · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.010 (human-in-the-loop modules price the approval push at $0.01/exec (venture model default) instead of the $0.001 machine default.)

## Permissions required

- `human:escalate`

## Provider setup

No external provider. Escalation record stored via ctx.memory_set after approval. Pair with human_notify to actually page the owner.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

Internal record only — creates the escalation after human approval. Does not itself page/message anyone; wire human_notify for delivery.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
