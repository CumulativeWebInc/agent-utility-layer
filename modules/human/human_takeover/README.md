# human_takeover (provisional name)

Transfer control of a task from the agent to a human operator.

Pillar: human · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.010 (human-in-the-loop modules price the approval push at $0.01/exec (venture model default) instead of the $0.001 machine default.)

## Permissions required

- `human:takeover`

## Provider setup

No external provider. Control-plane change recorded via ctx.memory_set (task_control:<task_id> = human) after approval.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

Control-plane change — the agent must stop acting on the task after transfer. Requires human approval (treated as destructive-adjacent). Enforcement of the agent stopping is the spine's job; this module records the transfer.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
