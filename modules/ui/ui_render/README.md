# ui_render (provisional name)

One-line purpose: turn agent JSON into styled, self-contained widget HTML —
`POST /v1/ui/render` from the concept doc.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a

## Permissions required

- `ui:render`

## Provider setup

No external provider. HTML/CSS/SVG is generated locally with stdlib only
(`html.escape`, `hashlib`, `json`) — no external requests, no JS libraries,
no CDN calls at render time. The rendered page is persisted in `ctx.memory`
under `aul:ui_render:{render_id}`, so the embed URL resolves to a real
artifact once deployed.

Component types:

- `data_table` — list of objects → styled table (columns unioned in order).
- `chart` — list of objects → server-side-rendered SVG bar chart (first
  numeric field is the value, first string field the label).
- `form` — object of `{name: {type, label, required}}` or list of field names
  → accessible HTML form.
- `confirmation_card` — object → summary card with Confirm/Cancel buttons.

Limits: 500 rows / 100KB per render; all user strings HTML-escaped.

## Honest limits

- **Real:** real HTML generation, real SVG charts, real XSS escaping, real
  persisted artifacts, deterministic `render_id` from the payload hash.
- **Not real / stubbed:** the CDN `embed_url` is a labeled placeholder until
  the deploy workstream provisions it — the `embed_url_note` and this README
  say so. Charts are static SVG (no interactivity). Demo runs against an
  in-memory FakeCtx, labeled "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling ui module.

© 2026 Cumulative Web Inc
