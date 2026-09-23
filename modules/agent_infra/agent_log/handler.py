"""agent_log: structured JSONL event log for agents (write + query)."""
import json
import os
import time
import uuid


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass

LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")


def _store_dir(ctx):
    d = getattr(ctx, "store_dir", None) or os.environ.get("AUL_STORE_DIR") \
        or os.path.expanduser("~/.aul/data")
    os.makedirs(d, exist_ok=True)
    return d


def _log_path(ctx):
    return os.path.join(_store_dir(ctx), "agent_log.jsonl")


def _iter_entries(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("write", "query", "tail"):
        raise ModuleError("op must be one of write|query|tail")
    path = _log_path(ctx)
    if op == "write":
        agent = inputs.get("agent")
        if not agent or not isinstance(agent, str):
            raise ModuleError("agent must be a non-empty string")
        level = inputs.get("level", "INFO")
        if level not in LEVELS:
            raise ModuleError(f"level must be one of {LEVELS}")
        event = inputs.get("event")
        if not event or not isinstance(event, str):
            raise ModuleError("event must be a non-empty string")
        data = inputs.get("data", {})
        if not isinstance(data, dict):
            raise ModuleError("data must be an object")
        # never log secrets: refuse keys that look like credentials
        for k in data:
            lk = str(k).lower()
            if any(s in lk for s in ("secret", "password", "token", "api_key", "apikey", "private_key")):
                raise ModuleError(f"refusing to log credential-like field: {k}")
        entry = {"entry_id": uuid.uuid4().hex, "ts": time.time(),
                 "agent": agent, "level": level, "event": event, "data": data}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return {"status": "ok", "entry_id": entry["entry_id"], "ts": entry["ts"]}
    # query / tail
    agent = inputs.get("agent")
    level = inputs.get("level")
    event = inputs.get("event")
    since_ts = inputs.get("since_ts")
    if level is not None and level not in LEVELS:
        raise ModuleError(f"level must be one of {LEVELS}")
    if since_ts is not None and not isinstance(since_ts, (int, float)):
        raise ModuleError("since_ts must be a number")
    limit = inputs.get("limit", 100)
    if not isinstance(limit, int) or limit < 1 or limit > 5000:
        raise ModuleError("limit must be an integer in [1, 5000]")
    matched = []
    for e in _iter_entries(path):
        if agent is not None and e.get("agent") != agent:
            continue
        if level is not None and e.get("level") != level:
            continue
        if event is not None and e.get("event") != event:
            continue
        if since_ts is not None and e.get("ts", 0) < since_ts:
            continue
        matched.append(e)
    matched.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return {"status": "ok", "entries": matched[:limit], "count": len(matched)}
