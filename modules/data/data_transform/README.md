# data_transform (provisional name)

Apply a pipeline of JSON transformations to a list of records. Real logic,
stdlib only.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |

## Permissions

- `data:transform`

## Inputs

- `data` (required) — list of objects
- `pipeline` (required) — non-empty list of op objects, applied in order

## Ops

| op | spec | effect |
|---|---|---|
| `filter` | `{"where": {...}}` | keep rows matching; bare value = `$eq`; operators `$eq $ne $gt $gte $lt $lte $in $contains` |
| `select` | `{"fields": [...]}` | project to listed fields |
| `rename` | `{"mapping": {old: new}}` | rename keys |
| `sort` | `{"by": "f", "desc": bool}` | sort by field (nulls last) |
| `limit` | `{"n": int}` | first N rows |
| `group_by` | `{"field": "f", "aggs": [...]}` | aggregate; each agg `{"fn": count\|sum\|avg\|min\|max, "field": "f", "as": "alias"}` |
| `flatten` | `{"sep": "."}` | flatten one level of nested objects into dotted keys |

## Honest limits

- In-memory only; no streaming — very large datasets are bounded by RAM.
- `sum`/`avg`/`min`/`max` require numeric values and fail loudly otherwise
  (no silent coercion). Input data is never mutated.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
