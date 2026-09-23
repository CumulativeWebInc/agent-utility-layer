"""agent_trace: span store with trace-tree assembly (sqlite-backed)."""
import json
import os
import sqlite3
import time
import uuid


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
    path = os.path.join(_store_dir(ctx), "agent_trace.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS spans ("
        " span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, parent_id TEXT,"
        " name TEXT NOT NULL, agent TEXT NOT NULL,"
        " started_at REAL NOT NULL, ended_at REAL,"
        " end_status TEXT, output_json TEXT)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans (trace_id)")
    return con


def _build_tree(rows):
    nodes = {}
    for r in rows:
        nodes[r[0]] = {"span_id": r[0], "trace_id": r[1], "parent_id": r[2],
                       "name": r[3], "agent": r[4], "started_at": r[5],
                       "ended_at": r[6], "end_status": r[7],
                       "output": json.loads(r[8]) if r[8] else None,
                       "children": []}
    roots = []
    for n in nodes.values():
        p = n["parent_id"]
        if p and p in nodes:
            nodes[p]["children"].append(n)
        else:
            roots.append(n)
    def _sort(n):
        n["children"].sort(key=lambda c: c["started_at"])
        for c in n["children"]:
            _sort(c)
    for r in roots:
        _sort(r)
    roots.sort(key=lambda r: r["started_at"])
    return roots


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("start", "end", "get_trace", "list_traces"):
        raise ModuleError("op must be one of start|end|get_trace|list_traces")
    now = time.time()
    con = _db(ctx)
    try:
        if op == "start":
            name = inputs.get("name")
            if not name or not isinstance(name, str):
                raise ModuleError("name must be a non-empty string")
            agent = inputs.get("agent")
            if not agent or not isinstance(agent, str):
                raise ModuleError("agent must be a non-empty string")
            trace_id = inputs.get("trace_id") or uuid.uuid4().hex
            span_id = inputs.get("span_id") or uuid.uuid4().hex
            parent_id = inputs.get("parent_id")
            if parent_id is not None and not isinstance(parent_id, str):
                raise ModuleError("parent_id must be a string")
            if parent_id:
                prow = con.execute("SELECT trace_id FROM spans WHERE span_id=?",
                                   (parent_id,)).fetchone()
                if prow is None:
                    raise ModuleError(f"parent span not found: {parent_id}")
                if prow[0] != trace_id:
                    raise ModuleError("parent span belongs to a different trace")
            try:
                con.execute(
                    "INSERT INTO spans (span_id, trace_id, parent_id, name, agent, started_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (span_id, trace_id, parent_id, name, agent, now))
            except sqlite3.IntegrityError:
                raise ModuleError(f"span_id already exists: {span_id}")
            con.commit()
            return {"status": "ok", "trace_id": trace_id, "span_id": span_id,
                    "started_at": now}
        if op == "end":
            span_id = inputs.get("span_id")
            if not span_id or not isinstance(span_id, str):
                raise ModuleError("span_id must be a non-empty string")
            row = con.execute("SELECT ended_at FROM spans WHERE span_id=?",
                              (span_id,)).fetchone()
            if row is None:
                raise ModuleError(f"span not found: {span_id}")
            if row[0] is not None:
                raise ModuleError(f"span already ended: {span_id}")
            end_status = inputs.get("end_status", "ok")
            if not isinstance(end_status, str) or not end_status:
                raise ModuleError("end_status must be a non-empty string")
            output = inputs.get("output")
            con.execute(
                "UPDATE spans SET ended_at=?, end_status=?, output_json=?"
                " WHERE span_id=?",
                (now, end_status, json.dumps(output) if output is not None else None,
                 span_id))
            con.commit()
            return {"status": "ok", "span_id": span_id, "ended_at": now,
                    "end_status": end_status}
        if op == "get_trace":
            trace_id = inputs.get("trace_id")
            if not trace_id or not isinstance(trace_id, str):
                raise ModuleError("trace_id must be a non-empty string")
            rows = con.execute(
                "SELECT span_id, trace_id, parent_id, name, agent, started_at,"
                " ended_at, end_status, output_json FROM spans"
                " WHERE trace_id=? ORDER BY started_at", (trace_id,)).fetchall()
            if not rows:
                return {"status": "ok", "found": False}
            return {"status": "ok", "found": True, "trace_id": trace_id,
                    "tree": _build_tree(rows), "span_count": len(rows)}
        # list_traces
        agent = inputs.get("agent")
        limit = inputs.get("limit", 50)
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ModuleError("limit must be an integer in [1, 500]")
        if agent:
            rows = con.execute(
                "SELECT trace_id, MIN(started_at), COUNT(*) FROM spans"
                " WHERE agent=? GROUP BY trace_id ORDER BY 2 DESC LIMIT ?",
                (agent, limit)).fetchall()
        else:
            rows = con.execute(
                "SELECT trace_id, MIN(started_at), COUNT(*) FROM spans"
                " GROUP BY trace_id ORDER BY 2 DESC LIMIT ?", (limit,)).fetchall()
        return {"status": "ok", "traces": [
            {"trace_id": r[0], "started_at": r[1], "span_count": r[2]} for r in rows]}
    finally:
        con.close()
