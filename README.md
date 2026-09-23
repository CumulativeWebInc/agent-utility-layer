# Agent Utility Layer — UNDER CONSTRUCTION

> **Provisional internal name.** Public brand names come from the screened-names
> workstream — no public brand name exists yet.

**Status: foundation in progress.** The spine (registry, execution API, auth,
permissions, billing, demo pages) is live in `spine/`. Capability modules land
under `modules/<pillar>/`; most are unbuilt. Zeros are zeros.

**What is real vs demo:**
- `spine/` — real, stdlib-only Python, tested.
- Demo pages (`docs/`) — labeled **DEMO — simulated providers**; never real provider results.
- `modules/_template/` — reference implementation proving the contract end to end
  (simulated provider, labeled).

## Layout

```
CONTRACT.md        module contract every capability follows
CATALOG.md         full 69-module catalog + crew assignments
REGISTRY.md        live tracker: module, pillar, price, tests, state, kill rule
spine/             execution spine (Crew A owns; module crews do not touch)
modules/_template/ reference module proving the contract end to end
modules/<pillar>/  capability modules (other crews)
docs/              generated demo site (GitHub Pages)
```

## Quickstart (spine)

```bash
# issue a dev API key (stored OUTSIDE the repo)
python3 -c "import sys; sys.path.insert(0,'spine'); from auth import KeyStore; print(KeyStore().issue('dev',['*']))"

# start the exec API (demo mode enabled)
AUL_DEMO=1 python3 spine/exec_api.py --port 8741

# list capabilities
curl localhost:8741/v1/capabilities

# execute (demo mode — simulated providers, clearly labeled)
curl -X POST localhost:8741/v1/execute \
  -H 'Content-Type: application/json' \
  -d '{"capability":"template_demo","inputs":{"message":"hello"},"agent_key":"<KEY>","demo":true}'
```

Pricing model: setup $1.00 · execution $0.001 · human approval $0.01.
Billed to a JSONL micro-ledger outside the repo.

## Honesty law

Demo results are never presented as live provider results. No fabricated
confirmations. No secrets in the repo, logs, or errors.

© 2026 Cumulative Web Inc
