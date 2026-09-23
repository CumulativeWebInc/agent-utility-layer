"""mem_short_term: ephemeral per-session key-value memory with TTL (sqlite-backed)."""
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
    path = os.path.join(_store_dir(ctx), "mem_short_term.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS kv ("
        " session_id TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL,"
        " expires_at REAL NOT NULL, PRIMARY KEY (session_id, key))"
    )
    return con


def _purge(con, now):
    con.execute("DELETE FROM kv WHERE expires_at <= ?", (now,))


def _need(inputs, *fields):
    for f in fields:
        if f not in inputs or inputs[f] is None or inputs[f] == "":
            raise ModuleError(f"missing required input: {f}")


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("set", "get", "list", "delete", "clear"):
        raise ModuleError("op must be one of set|get|list|delete|clear")
    now = time.time()
    con = _db(ctx)
    try:
        _purge(con, now)
        if op == "set":
            _need(inputs, "session_id", "key")
            if "value" not in inputs:
                raise ModuleError("missing required input: value")
            ttl = inputs.get("ttl_seconds", 3600)
            if not isinstance(ttl, (int, float)) or ttl <= 0:
                raise ModuleError("ttl_seconds must be a positive number")
            con.execute(
                "INSERT OR REPLACE INTO kv (session_id, key, value_json, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (inputs["session_id"], inputs["key"],
                 json.dumps(inputs["value"]), now + ttl),
            )
            con.commit()
            return {"status": "ok", "key": inputs["key"],
                    "expires_at": now + ttl}
        if op == "get":
            _need(inputs, "session_id", "key")
            row = con.execute(
                "SELECT value_json, expires_at FROM kv WHERE session_id=? AND key=?",
                (inputs["session_id"], inputs["key"])).fetchone()
            if row is None:
                return {"status": "ok", "found": False, "value": None}
            return {"status": "ok", "found": True,
                    "value": json.loads(row[0]), "expires_at": row[1]}
        if op == "list":
            _need(inputs, "session_id")
            rows = con.execute(
                "SELECT key, expires_at FROM kv WHERE session_id=? ORDER BY key",
                (inputs["session_id"],)).fetchall()
            return {"status": "ok",
                    "entries": [{"key": r[0], "expires_at": r[1]} for r in rows]}
        if op == "delete":
            _need(inputs, "session_id", "key")
            cur = con.execute(
                "DELETE FROM kv WHERE session_id=? AND key=?",
                (inputs["session_id"], inputs["key"]))
            con.commit()
            return {"status": "ok", "deleted": cur.rowcount}
        # clear
        _need(inputs, "session_id")
        cur = con.execute("DELETE FROM kv WHERE session_id=?",
                          (inputs["session_id"],))
        con.commit()
        return {"status": "ok", "cleared": cur.rowcount}
    finally:
        con.close()
