"""JSONL micro-ledger for the Agent Utility Layer.

Pricing model: setup $1.00 · execution $0.001 · human approval $0.01.

The ledger lives OUTSIDE the repo (default
~/.config/agent-utility-layer/ledger.jsonl, env AUL_LEDGER_FILE).
Only key fingerprints are recorded — never raw keys.
"""

import json
import os
import time
import uuid

LEDGER_ENV = "AUL_LEDGER_FILE"
DEFAULT_LEDGER_PATH = os.path.expanduser("~/.config/agent-utility-layer/ledger.jsonl")

SETUP_PRICE_USD = 1.00
EXEC_PRICE_USD = 0.001
APPROVAL_PRICE_USD = 0.01

KINDS = ("setup", "exec", "approval", "credit")


def ledger_path() -> str:
    return os.environ.get(LEDGER_ENV, DEFAULT_LEDGER_PATH)


def record(
    agent_id: str,
    capability: str,
    kind: str,
    amount_usd: float,
    memo: str = "",
    path: str | None = None,
) -> dict:
    """Append one ledger entry; return it."""
    if kind not in KINDS:
        raise ValueError(f"bad ledger kind: {kind!r}")
    entry = {
        "id": "lg_" + uuid.uuid4().hex[:12],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent_id": agent_id,  # fingerprint, never a raw key
        "capability": capability,
        "kind": kind,
        "amount_usd": round(float(amount_usd), 6),
        "memo": memo,
    }
    target = path or ledger_path()
    directory = os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(target, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def _iter(path: str | None = None):
    target = path or ledger_path()
    try:
        with open(target, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
    except FileNotFoundError:
        return


def total_for(agent_id: str, path: str | None = None) -> float:
    return round(sum(e["amount_usd"] for e in _iter(path) if e.get("agent_id") == agent_id), 6)


def totals_by_capability(agent_id: str | None = None, path: str | None = None) -> dict:
    out: dict[str, float] = {}
    for e in _iter(path):
        if agent_id is not None and e.get("agent_id") != agent_id:
            continue
        cap = e.get("capability", "?")
        out[cap] = round(out.get(cap, 0.0) + e["amount_usd"], 6)
    return out


def entry_count(path: str | None = None) -> int:
    return sum(1 for _ in _iter(path))
