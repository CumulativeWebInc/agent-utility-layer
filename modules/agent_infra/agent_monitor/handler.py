"""agent_monitor: agent heartbeat registry with staleness detection (sqlite-backed)."""
import json
import os
import sqlite3
import time


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _store_dir(ctx):
    d = getattr(ctx, "store_dir", None) or os.environ.get("AUL_STORE_DIR") \
        or os.path.expanduser("~/.aul/data")
    os.makedirs(d, exist_ok=True)
    return d


def _db(ctx):
    path = os.path.join(_store_dir(ctx), "agent_monitor.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS agents ("
        " agent TEXT PRIMARY KEY, status TEXT NOT NULL,"
        " last_heartbeat REAL NOT NULL, metrics_json TEXT NOT NULL DEFAULT '{}')"
    )
    return con


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("heartbeat", "status", "list", "deregister"):
        raise ModuleError("op must be one of heartbeat|status|list|deregister")
    now = time.time()
    con = _db(ctx)
    try:
        if op == "heartbeat":
            agent = inputs.get("agent")
            if not agent or not isinstance(agent, str):
                raise ModuleError("agent must be a non-empty string")
            status = inputs.get("status", "alive")
            if not isinstance(status, str) or not status:
                raise ModuleError("status must be a non-empty string")
            metrics = inputs.get("metrics", {})
            if not isinstance(metrics, dict):
                raise ModuleError("metrics must be an object")
            con.execute(
                "INSERT OR REPLACE INTO agents (agent, status, last_heartbeat, metrics_json)"
                " VALUES (?, ?, ?, ?)",
                (agent, status, now, json.dumps(metrics)))
            con.commit()
            return {"status": "ok", "agent": agent, "last_heartbeat": now}
        if op == "status":
            agent = inputs.get("agent")
            if not agent or not isinstance(agent, str):
                raise ModuleError("agent must be a non-empty string")
            stale_after = inputs.get("stale_after_s", 300)
            if not isinstance(stale_after, (int, float)) or stale_after <= 0:
                raise ModuleError("stale_after_s must be a positive number")
            row = con.execute(
                "SELECT status, last_heartbeat, metrics_json FROM agents WHERE agent=?",
                (agent,)).fetchone()
            if row is None:
                return {"status": "ok", "found": False}
            return {"status": "ok", "found": True, "agent": agent,
                    "agent_status": row[0], "last_heartbeat": row[1],
                    "metrics": json.loads(row[2]),
                    "stale": (now - row[1]) > stale_after,
                    "stale_after_s": stale_after}
        if op == "list":
            stale_after = inputs.get("stale_after_s", 300)
            if not isinstance(stale_after, (int, float)) or stale_after <= 0:
                raise ModuleError("stale_after_s must be a positive number")
            rows = con.execute(
                "SELECT agent, status, last_heartbeat, metrics_json FROM agents"
                " ORDER BY last_heartbeat DESC").fetchall()
            return {"status": "ok", "agents": [
                {"agent": r[0], "agent_status": r[1], "last_heartbeat": r[2],
                 "metrics": json.loads(r[3]), "stale": (now - r[2]) > stale_after}
                for r in rows]}
        agent = inputs.get("agent")
        if not agent or not isinstance(agent, str):
            raise ModuleError("agent must be a non-empty string")
        cur = con.execute("DELETE FROM agents WHERE agent=?", (agent,))
        con.commit()
        return {"status": "ok", "deleted": cur.rowcount}
    finally:
        con.close()
