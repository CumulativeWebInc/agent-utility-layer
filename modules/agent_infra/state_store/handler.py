"""state_store: namespaced KV with TTL and compare-and-set (sqlite-backed)."""
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
    path = os.path.join(_store_dir(ctx), "state_store.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS kv ("
        " namespace TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL,"
        " version INTEGER NOT NULL DEFAULT 1, expires_at REAL,"
        " PRIMARY KEY (namespace, key))")
    return con


def _purge(con, ns, now):
    con.execute(
        "DELETE FROM kv WHERE namespace=? AND expires_at IS NOT NULL"
        " AND expires_at <= ?", (ns, now))


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("set", "get", "delete", "list", "cas"):
        raise ModuleError("op must be one of set|get|delete|list|cas")
    ns = inputs.get("namespace")
    if not ns or not isinstance(ns, str):
        raise ModuleError("namespace must be a non-empty string")
    now = time.time()
    con = _db(ctx)
    try:
        _purge(con, ns, now)
        if op == "set":
            key = inputs.get("key")
            if not key or not isinstance(key, str):
                raise ModuleError("key must be a non-empty string")
            if "value" not in inputs:
                raise ModuleError("missing required input: value")
            ttl = inputs.get("ttl_seconds")
            if ttl is not None and (not isinstance(ttl, (int, float)) or ttl <= 0):
                raise ModuleError("ttl_seconds must be a positive number")
            row = con.execute(
                "SELECT version FROM kv WHERE namespace=? AND key=?",
                (ns, key)).fetchone()
            version = (row[0] + 1) if row else 1
            exp = now + ttl if ttl is not None else None
            con.execute(
                "INSERT OR REPLACE INTO kv (namespace, key, value_json, version, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (ns, key, json.dumps(inputs["value"]), version, exp))
            con.commit()
            return {"status": "ok", "key": key, "version": version}
        if op == "get":
            key = inputs.get("key")
            if not key or not isinstance(key, str):
                raise ModuleError("key must be a non-empty string")
            row = con.execute(
                "SELECT value_json, version, expires_at FROM kv"
                " WHERE namespace=? AND key=?", (ns, key)).fetchone()
            if row is None:
                return {"status": "ok", "found": False, "value": None}
            return {"status": "ok", "found": True, "value": json.loads(row[0]),
                    "version": row[1], "expires_at": row[2]}
        if op == "delete":
            key = inputs.get("key")
            if not key or not isinstance(key, str):
                raise ModuleError("key must be a non-empty string")
            cur = con.execute("DELETE FROM kv WHERE namespace=? AND key=?",
                              (ns, key))
            con.commit()
            return {"status": "ok", "deleted": cur.rowcount}
        if op == "list":
            prefix = inputs.get("prefix", "")
            if not isinstance(prefix, str):
                raise ModuleError("prefix must be a string")
            rows = con.execute(
                "SELECT key, version FROM kv WHERE namespace=? AND key LIKE ?"
                " ORDER BY key", (ns, prefix + "%")).fetchall()
            return {"status": "ok", "keys": [
                {"key": r[0], "version": r[1]} for r in rows]}
        # cas
        key = inputs.get("key")
        if not key or not isinstance(key, str):
            raise ModuleError("key must be a non-empty string")
        if "value" not in inputs:
            raise ModuleError("missing required input: value")
        exp_v = inputs.get("expected_version")
        if not isinstance(exp_v, int):
            raise ModuleError("expected_version must be an integer")
        row = con.execute(
            "SELECT version FROM kv WHERE namespace=? AND key=?",
            (ns, key)).fetchone()
        if row is None:
            raise ModuleError(f"key not found for cas: {key}")
        if row[0] != exp_v:
            raise ModuleError(
                f"version conflict: expected {exp_v}, current is {row[0]}")
        ttl = inputs.get("ttl_seconds")
        if ttl is not None and (not isinstance(ttl, (int, float)) or ttl <= 0):
            raise ModuleError("ttl_seconds must be a positive number")
        new_v = row[0] + 1
        exp = now + ttl if ttl is not None else None
        con.execute(
            "UPDATE kv SET value_json=?, version=?, expires_at=?"
            " WHERE namespace=? AND key=?",
            (json.dumps(inputs["value"]), new_v, exp, ns, key))
        con.commit()
        return {"status": "ok", "key": key, "version": new_v}
    finally:
        con.close()
