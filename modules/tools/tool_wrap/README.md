# tool_wrap (provisional name)

One-line purpose: convert any URL, OpenAPI document, or HTML page into an
OpenAI-style function spec for LLMs — `POST /v1/tools/wrap` from the concept doc.

## Pricing

- Setup: $1.00
- Per execution: **$1.00** (deviation from the $0.001 default, with reason: the
  concept doc bills each wrap at $1.00 — the wrap itself is the
  value-delivering call, so it carries the setup-tier price)
- Human-approval push: n/a

## Permissions required

- `tools:wrap`

## Provider setup

No external provider. The module fetches `target_url` with stdlib `urllib`
(10s timeout, 1MB cap), then parses:

1. **OpenAPI/Swagger JSON** → spec from the operation matching `method`
   (falls back to the first usable operation); parameters from query params
   and the JSON request body.
2. **HTML** → one spec per `<form>`; named inputs become parameters, `required`
   attributes become required fields.
3. **Anything else** → heuristic spec derived from the URL path, honestly
   labeled `heuristic_url`.

If `auth_type` is set (bearer/api_key/basic/header), the generated spec notes
that authentication is required at call time. The `auth_token` is validated
for presence and then **dropped** — never stored, logged, or returned.

## Honest limits

- **Real:** deterministic `tool_id` from URL+method hash; real HTTP fetch and
  real parse logic; a fetch failure raises `ModuleError` rather than returning
  a fabricated spec.
- **Not real / stubbed:** heuristic specs are labeled, not presented as
  parsed APIs. No credential vault — bring your own at execution time. Demo
  tests monkeypatch the fetcher and are labeled as fake.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling tools module.

© 2026 Cumulative Web Inc
