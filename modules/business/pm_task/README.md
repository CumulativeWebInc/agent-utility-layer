# pm_task (provisional name)

One-line purpose: create, assign, track, and complete project-management
tasks with status, priority, due dates, and subtasks in a JSON-backed store.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (internal store only)

## Permissions required

- `tasks:write`

## Provider setup

No external provider. Tasks live in the spine's scoped memory
(`ctx.memory`, key `aul:pm_tasks_v1`). An Asana/Linear/Jira connector would
sit behind `ctx.auth_get('pm')` — not present today.

## Honest limits

- **Real:** full task lifecycle — create, update, assign, subtasks, complete,
  reopen (done only), list/filter by project and status. Ids and timestamps
  are real; nothing is fabricated.
- **Not real / stubbed:** no sync to any external PM tool, no Gantt engine,
  no dependency graph. Demo runs against an in-memory FakeCtx, labeled
  "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
