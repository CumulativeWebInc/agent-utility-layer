"""task_queue: FIFO queue with lease semantics, priority, retries, dead-letter (sqlite)."""
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
    path = os.path.join(_store_dir(ctx), "task_queue.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        " id TEXT PRIMARY KEY, queue TEXT NOT NULL, payload_json TEXT NOT NULL,"
        " priority INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending',"
        " worker TEXT, lease_expires REAL, attempts INTEGER NOT NULL DEFAULT 0,"
        " last_error TEXT NOT NULL DEFAULT '',"
        " created_at REAL NOT NULL, updated_at REAL NOT NULL)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_q ON tasks (queue, status)")
    return con


def _row_to_task(r):
    return {"task_id": r[0], "queue": r[1], "payload": json.loads(r[2]),
            "priority": r[3], "status": r[4], "worker": r[5],
            "lease_expires": r[6], "attempts": r[7],
            "last_error": r[8], "created_at": r[9], "updated_at": r[10]}


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("enqueue", "lease", "complete", "fail", "stats", "purge_done"):
        raise ModuleError("op must be one of enqueue|lease|complete|fail|stats|purge_done")
    now = time.time()
    con = _db(ctx)
    try:
        if op == "enqueue":
            queue = inputs.get("queue")
            if not queue or not isinstance(queue, str):
                raise ModuleError("queue must be a non-empty string")
            payload = inputs.get("payload")
            if not isinstance(payload, dict):
                raise ModuleError("payload must be an object")
            prio = inputs.get("priority", 0)
            if not isinstance(prio, int):
                raise ModuleError("priority must be an integer")
            tid = uuid.uuid4().hex
            con.execute(
                "INSERT INTO tasks (id, queue, payload_json, priority, status,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (tid, queue, json.dumps(payload), prio, now, now))
            con.commit()
            return {"status": "ok", "task_id": tid}
        if op == "lease":
            queue = inputs.get("queue")
            if not queue or not isinstance(queue, str):
                raise ModuleError("queue must be a non-empty string")
            worker = inputs.get("worker")
            if not worker or not isinstance(worker, str):
                raise ModuleError("worker must be a non-empty string")
            lease_s = inputs.get("lease_seconds", 300)
            if not isinstance(lease_s, (int, float)) or lease_s <= 0:
                raise ModuleError("lease_seconds must be a positive number")
            row = con.execute(
                "SELECT id, queue, payload_json, priority, status, worker,"
                " lease_expires, attempts, last_error, created_at, updated_at"
                " FROM tasks WHERE queue=?"
                " AND (status='pending' OR (status='leased' AND lease_expires <= ?))"
                " ORDER BY priority DESC, created_at ASC LIMIT 1",
                (queue, now)).fetchone()
            if row is None:
                return {"status": "ok", "leased": False, "task": None}
            con.execute(
                "UPDATE tasks SET status='leased', worker=?, lease_expires=?,"
                " updated_at=? WHERE id=?",
                (worker, now + lease_s, now, row[0]))
            con.commit()
            task = _row_to_task(row)
            task["status"] = "leased"
            task["worker"] = worker
            task["lease_expires"] = now + lease_s
            return {"status": "ok", "leased": True, "task": task}
        if op == "complete":
            tid = inputs.get("task_id")
            if not tid or not isinstance(tid, str):
                raise ModuleError("task_id must be a non-empty string")
            row = con.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
            if row is None:
                raise ModuleError(f"task not found: {tid}")
            if row[0] not in ("leased", "pending"):
                raise ModuleError(f"task is {row[0]}, cannot complete")
            con.execute("UPDATE tasks SET status='done', updated_at=? WHERE id=?",
                        (now, tid))
            con.commit()
            return {"status": "ok", "task_id": tid}
        if op == "fail":
            tid = inputs.get("task_id")
            if not tid or not isinstance(tid, str):
                raise ModuleError("task_id must be a non-empty string")
            max_a = inputs.get("max_attempts", 5)
            if not isinstance(max_a, int) or max_a < 1:
                raise ModuleError("max_attempts must be a positive integer")
            err = inputs.get("error", "")
            if not isinstance(err, str):
                raise ModuleError("error must be a string")
            row = con.execute(
                "SELECT status, attempts FROM tasks WHERE id=?", (tid,)).fetchone()
            if row is None:
                raise ModuleError(f"task not found: {tid}")
            if row[0] not in ("leased", "pending"):
                raise ModuleError(f"task is {row[0]}, cannot fail")
            attempts = row[1] + 1
            new_status = "dead" if attempts >= max_a else "pending"
            con.execute(
                "UPDATE tasks SET status=?, attempts=?, last_error=?, worker=NULL,"
                " lease_expires=NULL, updated_at=? WHERE id=?",
                (new_status, attempts, err, now, tid))
            con.commit()
            return {"status": "ok", "task_id": tid, "attempts": attempts,
                    "new_status": new_status}
        if op == "stats":
            queue = inputs.get("queue")
            if not queue or not isinstance(queue, str):
                raise ModuleError("queue must be a non-empty string")
            rows = con.execute(
                "SELECT status, COUNT(*) FROM tasks WHERE queue=? GROUP BY status",
                (queue,)).fetchall()
            return {"status": "ok", "queue": queue,
                    "stats": {r[0]: r[1] for r in rows}}
        # purge_done
        queue = inputs.get("queue")
        if not queue or not isinstance(queue, str):
            raise ModuleError("queue must be a non-empty string")
        cur = con.execute("DELETE FROM tasks WHERE queue=? AND status='done'",
                          (queue,))
        con.commit()
        return {"status": "ok", "purged": cur.rowcount}
    finally:
        con.close()
