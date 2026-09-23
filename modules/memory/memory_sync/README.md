# memory_sync (provisional name)

One-line purpose: unified store/retrieve endpoint for cross-session user memory —
`POST /v1/memory/sync` from the concept doc.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (internal store only; nothing leaves the machine)

## Permissions required

- `memory:read`, `memory:write`

## Provider setup

No external provider. Memory lives in the spine's scoped store (`ctx.memory`,
key `aul:memory_sync_v1`) as a dict of `user_id -> {key: value}`. Crew H's
`mem_short_term` / `mem_long_term` modules are the underlying stores; this
module is the unified sync endpoint per the concept doc.

## Honest limits

- **Real:** store merges new keys into the user's memory dict; retrieve returns
  the full dict or a `context_keys` subset. Values must be JSON-serializable.
  Everything returned was previously stored through this module — nothing is
  fabricated or inferred.
- **Not real / stubbed:** there is no vector/semantic search, no TTL, no
  encryption-at-rest in this module (Crew H covers those lanes). The spine
  demo page runs this module against an in-memory FakeCtx and is labeled
  "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling memory module.

© 2026 Cumulative Web Inc
