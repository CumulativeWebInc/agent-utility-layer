"""convo_history: append-only conversation history per session (sqlite-backed)."""
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

ROLES = ("user", "assistant", "system", "tool")


def _store_dir(ctx):
    d = getattr(ctx, "store_dir", None) or os.environ.get("AUL_STORE_DIR") \
        or os.path.expanduser("~/.aul/data")
    os.makedirs(d, exist_ok=True)
    return d


def _db(ctx):
    path = os.path.join(_store_dir(ctx), "convo_history.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        " id TEXT PRIMARY KEY, session_id TEXT NOT NULL, user_id TEXT,"
        " role TEXT NOT NULL, content TEXT NOT NULL,"
        " metadata_json TEXT NOT NULL DEFAULT '{}', ts REAL NOT NULL)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id, ts)")
    return con


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("append", "history", "sessions", "clear", "search"):
        raise ModuleError("op must be one of append|history|sessions|clear|search")
    con = _db(ctx)
    try:
        if op == "append":
            if not inputs.get("session_id"):
                raise ModuleError("missing required input: session_id")
            role = inputs.get("role")
            if role not in ROLES:
                raise ModuleError(f"role must be one of {ROLES}")
            content = inputs.get("content")
            if not isinstance(content, str) or not content:
                raise ModuleError("content must be a non-empty string")
            meta = inputs.get("metadata", {})
            if not isinstance(meta, dict):
                raise ModuleError("metadata must be an object")
            mid = uuid.uuid4().hex
            ts = time.time()
            con.execute(
                "INSERT INTO messages (id, session_id, user_id, role, content,"
                " metadata_json, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, inputs["session_id"], inputs.get("user_id"), role,
                 content, json.dumps(meta), ts))
            con.commit()
            return {"status": "ok", "message_id": mid, "ts": ts}
        if op == "history":
            if not inputs.get("session_id"):
                raise ModuleError("missing required input: session_id")
            limit = inputs.get("limit", 50)
            if not isinstance(limit, int) or limit < 1 or limit > 1000:
                raise ModuleError("limit must be an integer in [1, 1000]")
            rows = con.execute(
                "SELECT id, role, content, metadata_json, ts, user_id FROM messages"
                " WHERE session_id=? ORDER BY ts ASC LIMIT ?",
                (inputs["session_id"], limit)).fetchall()
            return {"status": "ok", "messages": [
                {"id": r[0], "role": r[1], "content": r[2],
                 "metadata": json.loads(r[3]), "ts": r[4], "user_id": r[5]}
                for r in rows]}
        if op == "sessions":
            uid = inputs.get("user_id")
            if uid:
                rows = con.execute(
                    "SELECT DISTINCT session_id FROM messages WHERE user_id=?"
                    " ORDER BY session_id", (uid,)).fetchall()
            else:
                rows = con.execute(
                    "SELECT DISTINCT session_id FROM messages ORDER BY session_id"
                ).fetchall()
            return {"status": "ok", "sessions": [r[0] for r in rows]}
        if op == "clear":
            if not inputs.get("session_id"):
                raise ModuleError("missing required input: session_id")
            cur = con.execute("DELETE FROM messages WHERE session_id=?",
                              (inputs["session_id"],))
            con.commit()
            return {"status": "ok", "cleared": cur.rowcount}
        # search (substring, case-insensitive)
        q = inputs.get("query")
        if not q or not isinstance(q, str):
            raise ModuleError("query must be a non-empty string")
        sid = inputs.get("session_id")
        limit = inputs.get("limit", 50)
        if not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ModuleError("limit must be an integer in [1, 1000]")
        like = f"%{q}%"
        if sid:
            rows = con.execute(
                "SELECT id, session_id, role, content, metadata_json, ts FROM messages"
                " WHERE session_id=? AND content LIKE ?"
                " ORDER BY ts ASC LIMIT ?",
                (sid, like, limit)).fetchall()
        else:
            rows = con.execute(
                "SELECT id, session_id, role, content, metadata_json, ts FROM messages"
                " WHERE content LIKE ? ORDER BY ts ASC LIMIT ?", (like, limit)).fetchall()
        return {"status": "ok", "messages": [
            {"id": r[0], "session_id": r[1], "role": r[2], "content": r[3],
             "metadata": json.loads(r[4]), "ts": r[5]} for r in rows]}
    finally:
        con.close()
