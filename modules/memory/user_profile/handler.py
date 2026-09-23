"""user_profile: per-user profile document store with deep-merge updates."""
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
    path = os.path.join(_store_dir(ctx), "user_profile.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS profiles ("
        " user_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL DEFAULT '{}',"
        " updated_at REAL NOT NULL)"
    )
    return con


def _deep_merge(base, patch):
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _get_field(doc, dotted):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("get", "update", "get_field", "delete"):
        raise ModuleError("op must be one of get|update|get_field|delete")
    if not inputs.get("user_id"):
        raise ModuleError("missing required input: user_id")
    uid = inputs["user_id"]
    now = time.time()
    con = _db(ctx)
    try:
        if op == "update":
            patch = inputs.get("patch")
            if not isinstance(patch, dict):
                raise ModuleError("patch must be an object")
            row = con.execute(
                "SELECT profile_json FROM profiles WHERE user_id=?", (uid,)).fetchone()
            base = json.loads(row[0]) if row else {}
            merged = _deep_merge(base, patch)
            con.execute(
                "INSERT OR REPLACE INTO profiles (user_id, profile_json, updated_at)"
                " VALUES (?, ?, ?)", (uid, json.dumps(merged), now))
            con.commit()
            return {"status": "ok", "user_id": uid, "profile": merged}
        if op == "get":
            row = con.execute(
                "SELECT profile_json, updated_at FROM profiles WHERE user_id=?",
                (uid,)).fetchone()
            if row is None:
                return {"status": "ok", "found": False, "profile": {}}
            return {"status": "ok", "found": True, "profile": json.loads(row[0]),
                    "updated_at": row[1]}
        if op == "get_field":
            field = inputs.get("field")
            if not field or not isinstance(field, str):
                raise ModuleError("missing required input: field")
            row = con.execute(
                "SELECT profile_json FROM profiles WHERE user_id=?", (uid,)).fetchone()
            if row is None:
                return {"status": "ok", "found": False, "value": None}
            ok, val = _get_field(json.loads(row[0]), field)
            return {"status": "ok", "found": ok, "value": val}
        cur = con.execute("DELETE FROM profiles WHERE user_id=?", (uid,))
        con.commit()
        return {"status": "ok", "deleted": cur.rowcount}
    finally:
        con.close()
