"""mem_long_term: durable namespaced memory with importance + tags (sqlite-backed)."""
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
    path = os.path.join(_store_dir(ctx), "mem_long_term.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS facts ("
        " namespace TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL,"
        " importance REAL NOT NULL DEFAULT 0.5, tags_json TEXT NOT NULL DEFAULT '[]',"
        " updated_at REAL NOT NULL, PRIMARY KEY (namespace, key))"
    )
    return con


def _need(inputs, *fields):
    for f in fields:
        if f not in inputs or inputs[f] is None or inputs[f] == "":
            raise ModuleError(f"missing required input: {f}")


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("remember", "recall", "query", "forget", "namespaces"):
        raise ModuleError("op must be one of remember|recall|query|forget|namespaces")
    now = time.time()
    con = _db(ctx)
    try:
        if op == "remember":
            _need(inputs, "namespace", "key")
            if "value" not in inputs:
                raise ModuleError("missing required input: value")
            imp = inputs.get("importance", 0.5)
            if not isinstance(imp, (int, float)) or not 0.0 <= imp <= 1.0:
                raise ModuleError("importance must be a number in [0, 1]")
            tags = inputs.get("tags", [])
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise ModuleError("tags must be a list of strings")
            con.execute(
                "INSERT OR REPLACE INTO facts"
                " (namespace, key, value_json, importance, tags_json, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (inputs["namespace"], inputs["key"], json.dumps(inputs["value"]),
                 float(imp), json.dumps(tags), now),
            )
            con.commit()
            return {"status": "ok", "key": inputs["key"]}
        if op == "recall":
            _need(inputs, "namespace", "key")
            row = con.execute(
                "SELECT value_json, importance, tags_json, updated_at FROM facts"
                " WHERE namespace=? AND key=?",
                (inputs["namespace"], inputs["key"])).fetchone()
            if row is None:
                return {"status": "ok", "found": False, "value": None}
            return {"status": "ok", "found": True, "value": json.loads(row[0]),
                    "importance": row[1], "tags": json.loads(row[2]),
                    "updated_at": row[3]}
        if op == "query":
            _need(inputs, "namespace")
            tag = inputs.get("tag")
            min_imp = inputs.get("min_importance", 0.0)
            if not isinstance(min_imp, (int, float)):
                raise ModuleError("min_importance must be a number")
            rows = con.execute(
                "SELECT key, value_json, importance, tags_json, updated_at FROM facts"
                " WHERE namespace=? AND importance >= ?"
                " ORDER BY importance DESC, updated_at DESC LIMIT 200",
                (inputs["namespace"], float(min_imp))).fetchall()
            out = []
            for key, vj, imp, tj, ts in rows:
                tags = json.loads(tj)
                if tag is not None and tag not in tags:
                    continue
                out.append({"key": key, "value": json.loads(vj),
                            "importance": imp, "tags": tags, "updated_at": ts})
            return {"status": "ok", "entries": out}
        if op == "forget":
            _need(inputs, "namespace", "key")
            cur = con.execute("DELETE FROM facts WHERE namespace=? AND key=?",
                              (inputs["namespace"], inputs["key"]))
            con.commit()
            return {"status": "ok", "deleted": cur.rowcount}
        rows = con.execute(
            "SELECT DISTINCT namespace FROM facts ORDER BY namespace").fetchall()
        return {"status": "ok", "namespaces": [r[0] for r in rows]}
    finally:
        con.close()
