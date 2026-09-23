"""agent_analytics: real aggregations over the agent_log JSONL store."""
import json
import os
import time
from collections import Counter


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


def _scan(ctx, agent, cutoff):
    path = _log_path(ctx)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if agent is not None and e.get("agent") != agent:
                continue
            if cutoff is not None and e.get("ts", 0) < cutoff:
                continue
            out.append(e)
    return out


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("summary", "errors", "event_counts"):
        raise ModuleError("op must be one of summary|errors|event_counts")
    agent = inputs.get("agent")
    if agent is not None and (not isinstance(agent, str) or not agent):
        raise ModuleError("agent must be a non-empty string")
    window_hours = inputs.get("window_hours")
    if window_hours is None:
        cutoff = None
    else:
        if not isinstance(window_hours, (int, float)) or window_hours <= 0:
            raise ModuleError("window_hours must be a positive number")
        cutoff = time.time() - window_hours * 3600
    entries = _scan(ctx, agent, cutoff)
    if op == "errors":
        limit = inputs.get("limit", 20)
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ModuleError("limit must be an integer in [1, 1000]")
        errs = [e for e in entries if e.get("level") == "ERROR"]
        errs.sort(key=lambda e: e.get("ts", 0), reverse=True)
        return {"status": "ok", "count": len(errs), "entries": errs[:limit]}
    if op == "event_counts":
        event = inputs.get("event")
        if event is not None and (not isinstance(event, str) or not event):
            raise ModuleError("event must be a non-empty string")
        c = Counter(e.get("event") for e in entries
                    if event is None or e.get("event") == event)
        return {"status": "ok", "total": len(entries),
                "counts": dict(c.most_common(100))}
    # summary
    by_level = Counter(e.get("level", "UNKNOWN") for e in entries)
    by_event = Counter(e.get("event", "UNKNOWN") for e in entries)
    total = len(entries)
    err_n = by_level.get("ERROR", 0)
    return {"status": "ok", "total": total,
            "by_level": dict(by_level),
            "by_event": [{"event": ev, "count": n}
                         for ev, n in by_event.most_common(10)],
            "error_rate": (err_n / total) if total else 0.0,
            "window_hours": window_hours}
