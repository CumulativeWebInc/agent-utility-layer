# identity_verify (provisional name)

Identity verification case workflow: start -> submit_evidence -> decision (approve/reject) -> status.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `identity:verify`

## Provider setup
No provider. Cases live in ctx.memory; evidence is recorded by reference (type + storage ref).

## Approval
decision requires ctx.approval_request (irreversible verdict). Others do not.

## Honest limits
- Honest limit: v1 records and tracks evidence — it does NOT biometrically or document-AI verify anything itself. The 'decision' is a recorded human/operator verdict with an approval gate.
- State machine enforced: evidence only on pending cases, decision only once, then terminal.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
