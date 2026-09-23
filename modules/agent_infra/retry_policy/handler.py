"""retry_policy: real backoff math + dead-letter store.

HONEST: this module computes delays; it does NOT sleep or retry anything itself.
The caller executes retries using the computed delays. Dead-letter is persistent.
"""
import json
import os
import random
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
    path = os.path.join(_store_dir(ctx), "retry_policy.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS attempts ("
        " operation_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0,"
        " last_error TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL)")
    con.execute(
        "CREATE TABLE IF NOT EXISTS dead_letter ("
        " operation_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL,"
        " last_error TEXT NOT NULL DEFAULT '', dead_at REAL NOT NULL)")
    return con


def _validate_policy(p):
    if not isinstance(p, dict):
        raise ModuleError("policy must be an object")
    max_attempts = p.get("max_attempts", 3)
    base = p.get("base_delay_s", 1.0)
    backoff = p.get("backoff", "exponential")
    factor = p.get("factor", 2.0)
    jitter = p.get("jitter_s", 0.0)
    max_delay = p.get("max_delay_s", 300.0)
    if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 20:
        raise ModuleError("policy.max_attempts must be an integer in [1, 20]")
    if not isinstance(base, (int, float)) or base < 0:
        raise ModuleError("policy.base_delay_s must be a non-negative number")
    if backoff not in ("linear", "exponential", "constant"):
        raise ModuleError("policy.backoff must be linear|exponential|constant")
    if not isinstance(factor, (int, float)) or factor < 1:
        raise ModuleError("policy.factor must be >= 1")
    if not isinstance(jitter, (int, float)) or jitter < 0:
        raise ModuleError("policy.jitter_s must be a non-negative number")
    if not isinstance(max_delay, (int, float)) or max_delay <= 0:
        raise ModuleError("policy.max_delay_s must be a positive number")
    return {"max_attempts": max_attempts, "base_delay_s": float(base),
            "backoff": backoff, "factor": float(factor),
            "jitter_s": float(jitter), "max_delay_s": float(max_delay)}


def _delay(p, attempt, rng):
    # attempt is 1-based: delay BEFORE retry number `attempt`
    if p["backoff"] == "constant":
        d = p["base_delay_s"]
    elif p["backoff"] == "linear":
        d = p["base_delay_s"] * attempt
    else:
        d = p["base_delay_s"] * (p["factor"] ** (attempt - 1))
    if p["jitter_s"] > 0:
        d += rng.uniform(0, p["jitter_s"])
    return min(d, p["max_delay_s"])


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("plan", "next_delay", "record_failure", "dead_letter", "requeue"):
        raise ModuleError(
            "op must be one of plan|next_delay|record_failure|dead_letter|requeue")
    seed = inputs.get("seed")
    rng = random.Random(seed) if isinstance(seed, int) else random.Random()
    if op == "plan":
        p = _validate_policy(inputs.get("policy"))
        delays = [round(_delay(p, a, rng), 6)
                  for a in range(1, p["max_attempts"])]
        return {"status": "ok", "policy": p, "delays": delays}
    if op == "next_delay":
        p = _validate_policy(inputs.get("policy"))
        attempt = inputs.get("attempt")
        if not isinstance(attempt, int) or attempt < 1:
            raise ModuleError("attempt must be a positive integer")
        if attempt >= p["max_attempts"]:
            return {"status": "ok", "delay_seconds": 0.0,
                    "exhausted": True, "attempt": attempt}
        return {"status": "ok",
                "delay_seconds": round(_delay(p, attempt, rng), 6),
                "exhausted": False, "attempt": attempt}
    con = _db(ctx)
    try:
        now = time.time()
        if op == "record_failure":
            op_id = inputs.get("operation_id")
            if not op_id or not isinstance(op_id, str):
                raise ModuleError("operation_id must be a non-empty string")
            p = _validate_policy(inputs.get("policy"))
            err = inputs.get("error", "")
            if not isinstance(err, str):
                raise ModuleError("error must be a string")
            row = con.execute(
                "SELECT attempts FROM attempts WHERE operation_id=?",
                (op_id,)).fetchone()
            attempts = (row[0] if row else 0) + 1
            con.execute(
                "INSERT OR REPLACE INTO attempts"
                " (operation_id, attempts, last_error, updated_at)"
                " VALUES (?, ?, ?, ?)", (op_id, attempts, err, now))
            dead = attempts >= p["max_attempts"]
            if dead:
                con.execute(
                    "INSERT OR REPLACE INTO dead_letter"
                    " (operation_id, attempts, last_error, dead_at)"
                    " VALUES (?, ?, ?, ?)", (op_id, attempts, err, now))
                con.execute("DELETE FROM attempts WHERE operation_id=?", (op_id,))
            con.commit()
            return {"status": "ok", "operation_id": op_id, "attempts": attempts,
                    "dead_lettered": dead}
        if op == "dead_letter":
            rows = con.execute(
                "SELECT operation_id, attempts, last_error, dead_at FROM dead_letter"
                " ORDER BY dead_at DESC LIMIT 200").fetchall()
            return {"status": "ok", "entries": [
                {"operation_id": r[0], "attempts": r[1],
                 "last_error": r[2], "dead_at": r[3]} for r in rows]}
        # requeue
        op_id = inputs.get("operation_id")
        if not op_id or not isinstance(op_id, str):
            raise ModuleError("operation_id must be a non-empty string")
        cur = con.execute("DELETE FROM dead_letter WHERE operation_id=?", (op_id,))
        con.execute(
            "INSERT OR REPLACE INTO attempts (operation_id, attempts, last_error, updated_at)"
            " VALUES (?, 0, '', ?)", (op_id, now))
        con.commit()
        return {"status": "ok", "requeued": cur.rowcount > 0}
    finally:
        con.close()
