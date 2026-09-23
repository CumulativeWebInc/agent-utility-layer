"""job_schedule: cron/interval schedules with real due-job computation (sqlite-backed).

HONEST: this module never executes jobs. The spine polls `due` and dispatches.
Cron supports *, */n, lists, ranges (numeric fields; no month/day names).
All times are UTC epoch seconds.
"""
import calendar
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

_INTERVAL = re.compile(r"^every\s+(\d+)\s*([smhd])$", re.IGNORECASE)


def _store_dir(ctx):
    d = getattr(ctx, "store_dir", None) or os.environ.get("AUL_STORE_DIR") \
        or os.path.expanduser("~/.aul/data")
    os.makedirs(d, exist_ok=True)
    return d


def _db(ctx):
    path = os.path.join(_store_dir(ctx), "job_schedule.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS jobs ("
        " name TEXT PRIMARY KEY, schedule TEXT NOT NULL,"
        " payload_json TEXT NOT NULL DEFAULT '{}', enabled INTEGER NOT NULL DEFAULT 1,"
        " next_run REAL, last_run REAL)")
    return con


def _parse_field(field, lo, hi):
    vals = set()
    for part in field.split(","):
        part = part.strip()
        if part == "*":
            vals.update(range(lo, hi + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            if step < 1:
                raise ModuleError(f"bad cron step: {part}")
            vals.update(range(lo, hi + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if not (lo <= a <= b <= hi):
                raise ModuleError(f"cron range out of bounds: {part}")
            vals.update(range(a, b + 1))
        else:
            v = int(part)
            if not lo <= v <= hi:
                raise ModuleError(f"cron value out of bounds: {part}")
            vals.add(v)
    if not vals:
        raise ModuleError(f"empty cron field: {field}")
    return vals


def _parse_cron(expr):
    parts = expr.split()
    if len(parts) != 5:
        raise ModuleError("cron schedule must have 5 fields: 'min hour dom month dow'")
    try:
        return (
            _parse_field(parts[0], 0, 59),
            _parse_field(parts[1], 0, 23),
            _parse_field(parts[2], 1, 31),
            _parse_field(parts[3], 1, 12),
            _parse_field(parts[4], 0, 6),  # 0=Sunday
        )
    except ValueError:
        raise ModuleError(f"invalid cron expression: {expr}")


def _cron_next(expr, after):
    minute, hour, dom, month, dow = _parse_cron(expr)
    # minute-resolution scan, capped at ~366 days
    t = int(after) - (int(after) % 60) + 60
    limit = t + 366 * 86400
    while t <= limit:
        dt = time.gmtime(t)
        py_dow = (dt.tm_wday + 1) % 7  # Monday=0 -> Sunday=0
        if (dt.tm_min in minute and dt.tm_hour in hour and dt.tm_mday in dom
                and dt.tm_mon in month and py_dow in dow):
            return float(t)
        t += 60
    raise ModuleError("no cron occurrence within 366 days")


def _interval_seconds(expr):
    m = _INTERVAL.match(expr.strip())
    if not m:
        return None
    n = int(m.group(1))
    if n < 1:
        raise ModuleError("interval must be >= 1")
    unit = m.group(2).lower()
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _next_run(schedule, after):
    secs = _interval_seconds(schedule)
    if secs is not None:
        return float(int(after) + secs)
    return _cron_next(schedule, after)


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("create", "list", "due", "mark_run", "delete", "next_runs"):
        raise ModuleError("op must be one of create|list|due|mark_run|delete|next_runs")
    now = time.time()
    con = _db(ctx)
    try:
        if op == "create":
            name = inputs.get("name")
            if not name or not isinstance(name, str):
                raise ModuleError("name must be a non-empty string")
            schedule = inputs.get("schedule")
            if not schedule or not isinstance(schedule, str):
                raise ModuleError("schedule must be a non-empty string")
            payload = inputs.get("payload", {})
            if not isinstance(payload, dict):
                raise ModuleError("payload must be an object")
            enabled = inputs.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ModuleError("enabled must be a boolean")
            nxt = _next_run(schedule, now)  # validates the schedule
            con.execute(
                "INSERT OR REPLACE INTO jobs"
                " (name, schedule, payload_json, enabled, next_run, last_run)"
                " VALUES (?, ?, ?, ?, ?, NULL)",
                (name, schedule, json.dumps(payload), int(enabled), nxt))
            con.commit()
            return {"status": "ok", "name": name, "next_run": nxt}
        if op == "list":
            rows = con.execute(
                "SELECT name, schedule, payload_json, enabled, next_run, last_run"
                " FROM jobs ORDER BY name").fetchall()
            return {"status": "ok", "jobs": [
                {"name": r[0], "schedule": r[1], "payload": json.loads(r[2]),
                 "enabled": bool(r[3]), "next_run": r[4], "last_run": r[5]}
                for r in rows]}
        if op == "due":
            at = inputs.get("now_ts", now)
            if not isinstance(at, (int, float)):
                raise ModuleError("now_ts must be a number")
            rows = con.execute(
                "SELECT name, schedule, payload_json, next_run FROM jobs"
                " WHERE enabled=1 AND next_run IS NOT NULL AND next_run <= ?"
                " ORDER BY next_run", (at,)).fetchall()
            return {"status": "ok", "now": at, "due": [
                {"name": r[0], "schedule": r[1], "payload": json.loads(r[2]),
                 "next_run": r[3]} for r in rows]}
        if op == "mark_run":
            name = inputs.get("name")
            if not name or not isinstance(name, str):
                raise ModuleError("name must be a non-empty string")
            at = inputs.get("now_ts", now)
            if not isinstance(at, (int, float)):
                raise ModuleError("now_ts must be a number")
            row = con.execute("SELECT schedule FROM jobs WHERE name=?",
                              (name,)).fetchone()
            if row is None:
                raise ModuleError(f"job not found: {name}")
            nxt = _next_run(row[0], at)
            con.execute("UPDATE jobs SET last_run=?, next_run=? WHERE name=?",
                        (at, nxt, name))
            con.commit()
            return {"status": "ok", "name": name, "next_run": nxt}
        if op == "delete":
            name = inputs.get("name")
            if not name or not isinstance(name, str):
                raise ModuleError("name must be a non-empty string")
            cur = con.execute("DELETE FROM jobs WHERE name=?", (name,))
            con.commit()
            return {"status": "ok", "deleted": cur.rowcount}
        # next_runs: recompute from now for every job (read-only preview)
        at = inputs.get("now_ts", now)
        if not isinstance(at, (int, float)):
            raise ModuleError("now_ts must be a number")
        rows = con.execute("SELECT name, schedule FROM jobs ORDER BY name").fetchall()
        return {"status": "ok", "jobs": [
            {"name": r[0], "schedule": r[1], "next_run": _next_run(r[1], at)}
            for r in rows]}
    finally:
        con.close()
