"""error_recovery: recovery playbook registry with regex-matched suggestions.

Suggestions are advisory text. This module never executes recovery steps itself.
"""
import json
import os
import re
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
    path = os.path.join(_store_dir(ctx), "error_recovery.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS playbooks ("
        " error_class TEXT PRIMARY KEY, match_regex TEXT NOT NULL DEFAULT '',"
        " steps_json TEXT NOT NULL, created_at REAL NOT NULL)")
    con.execute(
        "CREATE TABLE IF NOT EXISTS recovery_log ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, error_class TEXT NOT NULL,"
        " action TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT '', ts REAL NOT NULL)")
    return con


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("register", "suggest", "list", "log_recovery"):
        raise ModuleError("op must be one of register|suggest|list|log_recovery")
    now = time.time()
    con = _db(ctx)
    try:
        if op == "register":
            ec = inputs.get("error_class")
            if not ec or not isinstance(ec, str):
                raise ModuleError("error_class must be a non-empty string")
            steps = inputs.get("steps")
            if not isinstance(steps, list) or not steps or \
                    not all(isinstance(s, str) and s for s in steps):
                raise ModuleError("steps must be a non-empty list of strings")
            regex = inputs.get("match_regex", "")
            if not isinstance(regex, str):
                raise ModuleError("match_regex must be a string")
            if regex:
                try:
                    re.compile(regex)
                except re.error as e:
                    raise ModuleError(f"invalid match_regex: {e}")
            con.execute(
                "INSERT OR REPLACE INTO playbooks"
                " (error_class, match_regex, steps_json, created_at)"
                " VALUES (?, ?, ?, ?)",
                (ec, regex, json.dumps(steps), now))
            con.commit()
            return {"status": "ok", "error_class": ec, "steps": len(steps)}
        if op == "suggest":
            ec = inputs.get("error_class")
            message = inputs.get("message", "")
            if message is not None and not isinstance(message, str):
                raise ModuleError("message must be a string")
            if ec:
                rows = con.execute(
                    "SELECT error_class, match_regex, steps_json FROM playbooks"
                    " WHERE error_class=?", (ec,)).fetchall()
            else:
                rows = con.execute(
                    "SELECT error_class, match_regex, steps_json FROM playbooks").fetchall()
            suggestions = []
            for cls, rx, sj in rows:
                matched = True
                if rx and message:
                    try:
                        matched = re.search(rx, message) is not None
                    except re.error:
                        matched = False
                if matched:
                    suggestions.append({"error_class": cls,
                                        "steps": json.loads(sj)})
            return {"status": "ok", "suggestions": suggestions}
        if op == "list":
            rows = con.execute(
                "SELECT error_class, match_regex, created_at FROM playbooks"
                " ORDER BY error_class").fetchall()
            return {"status": "ok", "playbooks": [
                {"error_class": r[0], "match_regex": r[1], "created_at": r[2]}
                for r in rows]}
        # log_recovery
        ec = inputs.get("error_class")
        if not ec or not isinstance(ec, str):
            raise ModuleError("error_class must be a non-empty string")
        action = inputs.get("action")
        if not action or not isinstance(action, str):
            raise ModuleError("action must be a non-empty string")
        outcome = inputs.get("outcome", "")
        if not isinstance(outcome, str):
            raise ModuleError("outcome must be a string")
        con.execute(
            "INSERT INTO recovery_log (error_class, action, outcome, ts)"
            " VALUES (?, ?, ?, ?)", (ec, action, outcome, now))
        con.commit()
        return {"status": "ok"}
    finally:
        con.close()
