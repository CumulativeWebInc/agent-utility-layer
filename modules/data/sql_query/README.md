# sql_query (provisional name)

Run SQL against a SQLite database via stdlib `sqlite3`. Read-only by
default; write statements require human approval before anything executes.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |
| Human approval | $0.01 (only for write statements with `read_only=false`) |

## Permissions

- `data:query`

## Inputs

- `query` (required) — single SQL statement; parameterized via `params`
- `db_base64` **or** `db_path` (one required) — SQLite file bytes or path
- `params` — optional list of bound parameters (prevents SQL injection)
- `read_only` — default `true`: only `SELECT`/`WITH`/`EXPLAIN`/`PRAGMA`
- `max_rows` — default 1,000; overflow is cut and flagged `truncated`

## Honest limits

- SQLite only — no Postgres/MySQL wire protocols in this module.
- Read-only mode refuses any write statement outright (no approval dance).
- With `read_only=false`, `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/…`
  statements call `ctx.approval_request` FIRST; a denial raises
  `ApprovalDenied` and nothing runs.
- Single-statement queries only; multi-statement strings are rejected.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
