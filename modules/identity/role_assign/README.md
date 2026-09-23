# role_assign (provisional name)

Assign or revoke RBAC roles for a principal (admin/operator/viewer/auditor).

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `identity:rbac`

## Provider setup
No provider. Writes to the ctx.memory RBAC store consumed by permission_check.

## Approval
assign/revoke require ctx.approval_request (security-sensitive). list does not.

## Honest limits
- Fixed role vocabulary in v1: admin, operator, viewer, auditor. Unknown role -> ModuleError.
- Assigning 'admin' is a privileged change and is flagged in the approval summary.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
