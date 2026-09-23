# nosql_query (provisional name)

A JSON document store with insert/find/update/delete/drop/count over named
collections, persisted in the agent's scoped memory. Real CRUD — no stubs.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |
| Human approval | $0.01 (only for `delete` and `drop`) |

## Permissions

- `data:query`

## Inputs

- `operation` (required) — `insert`, `find`, `update`, `delete`, `drop`,
  `count`, `list_collections`
- `collection` — required for all except `list_collections`
- `document` — object, for `insert`
- `filter` — object, for `find`/`update`/`delete`/`count`. Bare values mean
  equality; operator objects supported: `$eq $ne $gt $gte $lt $lte $in $contains`
- `update` — object of fields to set, for `update`
- `limit` — default 100, for `find`

## Honest limits

- Persistence is the agent's scoped memory (`ctx.memory_get/set`) — it lasts
  as long as the runtime's memory does, not a durable database. For durable
  storage, export via another path.
- `delete` and `drop` call `ctx.approval_request` FIRST; denial raises
  `ApprovalDenied` and nothing is removed.
- Inserted documents get an `_id` (uuid hex) unless one is provided; `update`
  never changes `_id`.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
