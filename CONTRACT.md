# Agent Utility Layer — Module Contract v1.0.0

Every capability module conforms to this contract so the spine (registry, execution API,
permissions, billing, demo pages) can load it without custom integration code.

## Directory layout

```
~/workspace/cwi-company/agent-utility-layer/
  CONTRACT.md            # this file
  CATALOG.md             # full module catalog + crew assignments
  spine/                 # owned by the SPINE crew only — module crews do not touch
    exec_api.py          # POST /v1/execute, GET /v1/capabilities
    registry.py          # loads modules/*/capability.json, validates
    permissions.py       # permission declarations + enforcement
    auth.py              # API-key auth (keys file, never in repo)
    billing.py           # JSONL micro-ledger
    demo.py              # auto-generates demo HTML per module from capability.json
  modules/<pillar>/<module_name>/
    capability.json      # manifest (schema below)
    handler.py           # def execute(inputs: dict, ctx) -> dict
    test_handler.py      # pytest, ≥5 tests incl. failure paths
    README.md            # pricing, permissions, honest limits, © notice
    manifest.json        # crew-written build receipt (see below)
```

Module crews work ONLY under `modules/<their pillar>/`. Never touch `spine/`.
Provisional internal names are snake_case (e.g. `send_email`). Public brand names
are applied later from the screened-names workstream — never invent public brand names.

## capability.json

```json
{
  "name": "send_email",
  "provisional": true,
  "pillar": "communication",
  "version": "0.1.0",
  "description": "Send an email via the configured provider.",
  "permissions": ["email:send"],
  "inputs_schema": {
    "type": "object",
    "properties": {
      "to": {"type": "string"},
      "subject": {"type": "string"},
      "body": {"type": "string"}
    },
    "required": ["to", "subject", "body"]
  },
  "outputs_schema": {
    "type": "object",
    "properties": {
      "status": {"type": "string"},
      "message_id": {"type": "string"}
    }
  },
  "setup_price_usd": 1.00,
  "price_per_execution_usd": 0.001,
  "provider_notes": "SMTP via stdlib smtplib; credentials from ctx.auth_get('smtp')."
}
```

Pricing defaults from the venture model: setup $1.00, execution $0.001,
human-approval push $0.01. Deviate only with a reason written in README.

## handler.py

```python
def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed (documented below).
    - Validate inputs against inputs_schema; raise ModuleError on bad input.
    - Return a dict matching outputs_schema.
    - NEVER fabricate provider results. No credential -> raise AuthMissing
      with setup instructions. Tests/demo use fake providers, clearly labeled.
    """

class ModuleError(Exception): pass
class AuthMissing(ModuleError): pass
class ApprovalDenied(ModuleError): pass
```

### ctx interface (provided by spine at runtime; crews test with a FakeCtx)

- `ctx.auth_get(provider: str) -> str` — credential string; raises `AuthMissing` if unconfigured.
- `ctx.approval_request(summary: str, timeout_seconds: int = 300) -> str` — returns approval id; raises `ApprovalDenied` if the human says no. Use for spend, external sends, destructive actions.
- `ctx.memory_get(key: str)` / `ctx.memory_set(key: str, value)` — scoped key-value.
- `ctx.log(event: str, data: dict)` — structured log line.
- `ctx.bill(amount_usd: float, memo: str)` — record micro-charge.

Rules: external sends (email/SMS/etc.), spend, and destructive actions REQUIRE
`ctx.approval_request` first. Secrets never logged, never in errors, never in repo.

## Tests

`test_handler.py`, pytest, stdlib + pytest only. Minimum per module:
1. happy path with FakeCtx (fake provider),
2. invalid inputs → ModuleError,
3. missing credential → AuthMissing (where a provider is needed),
4. approval-required path → ApprovalDenied when fake denies (where applicable),
5. outputs match outputs_schema keys.

All green before the module is claimed done. `python3 -m pytest modules/<pillar>/<module>/ -q`.

## README.md (per module)

Provisional name, one-line purpose, pricing, permissions required,
provider setup, honest limits (what is real vs stubbed/demo), kill rule,
and `© 2026 Cumulative Web Inc`.

## manifest.json (build receipt, written by the crew)

```json
{
  "module": "send_email",
  "crew": "C",
  "tests": "12 passed",
  "honest_state": "code-complete, providers-live-via-smtp | demo-fakes-labeled",
  "price_setup_usd": 1.00,
  "price_per_exec_usd": 0.001,
  "kill_rule": "no real usage in 60 days -> kill or merge",
  "notes": "..."
}
```

## Honesty law

- Demo mode (spine demo pages) runs modules against sandbox fakes and is labeled
  "DEMO — simulated providers" on the page itself.
- Never present a demo/fake result as a live provider result.
- Real provider paths use stdlib only (urllib, smtplib, etc.) with credentials
  from ctx — no hardcoded secrets, no fake "sent" confirmations.
- Zeros are zeros. Unbuilt = unbuilt.

## Kill rule (per module)

No real usage within 60 days of listing → kill the module or merge it into a
sibling. Recorded in the registry; never silently kept.
