# permission_check (provisional name)

Evaluate an RBAC allow/deny for a principal, action, and resource against stored grants.

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `identity:rbac`

## Provider setup
No provider. Reads role assignments + grants from ctx.memory (written by role_assign).

## Approval
None required.

## Honest limits
- Default-deny: unknown principal or no matching grant -> allowed:false.
- Wildcard '*' supported in grant resource patterns and actions.
- Read-only evaluation — it never mutates grants (that's role_assign).

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
