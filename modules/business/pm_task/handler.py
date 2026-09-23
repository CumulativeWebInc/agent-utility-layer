"""pm_task — project task CRUD with status, priority, due dates, subtasks.

Store key: "aul:pm_tasks_v1" via ctx.memory. Real bookkeeping only —
nothing is fabricated; unknown ids raise ModuleError.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

EXEC_PRICE_USD = 0.001
STORE_KEY = "aul:pm_tasks_v1"

ACTIONS = {"create", "get", "update", "complete", "reopen", "assign", "add_subtask", "list"}
STATUSES = {"todo", "in_progress", "blocked", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}
UPDATE_FIELDS = {"title", "description", "status", "priority", "assignee", "due_date", "project", "tags"}


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(ctx) -> dict:
    store = ctx.memory_get(STORE_KEY)
    return dict(store) if isinstance(store, dict) else {}


def _save(ctx, store: dict) -> None:
    ctx.memory_set(STORE_KEY, store)


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError("invalid action %r; must be one of %s" % (action, sorted(ACTIONS)))

    store = _load(ctx)
    ctx.log("pm_task.action", {"action": action})

    def _task_or_raise(tid):
        if not tid:
            raise ModuleError("task_id is required")
        t = store.get(tid)
        if t is None:
            raise ModuleError("no task found with id %r" % tid)
        return t

    if action == "create":
        data = inputs.get("data")
        if not isinstance(data, dict):
            raise ModuleError("data must be an object for create")
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ModuleError("data.title is required (non-empty string)")
        priority = data.get("priority", "medium")
        if priority not in PRIORITIES:
            raise ModuleError("priority must be one of %s" % sorted(PRIORITIES))
        tid = "task_" + uuid.uuid4().hex[:12]
        task = {
            "id": tid,
            "title": title.strip(),
            "description": data.get("description", ""),
            "project": data.get("project", ""),
            "status": "todo",
            "priority": priority,
            "assignee": data.get("assignee", ""),
            "due_date": data.get("due_date", ""),
            "tags": list(data.get("tags", [])) if isinstance(data.get("tags"), list) else [],
            "subtasks": [],
            "created_at": _now(),
            "updated_at": _now(),
            "completed_at": None,
        }
        store[tid] = task
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "pm_task create")
        return {"status": "created", "task": task, "tasks": [], "count": 1}

    if action == "get":
        t = _task_or_raise(inputs.get("task_id"))
        ctx.bill(EXEC_PRICE_USD, "pm_task get")
        return {"status": "ok", "task": t, "tasks": [], "count": 1}

    if action == "update":
        t = _task_or_raise(inputs.get("task_id"))
        data = inputs.get("data")
        if not isinstance(data, dict) or not data:
            raise ModuleError("data must be a non-empty object for update")
        for k in data:
            if k not in UPDATE_FIELDS:
                raise ModuleError("cannot update field %r; allowed: %s" % (k, sorted(UPDATE_FIELDS)))
        if "status" in data and data["status"] not in STATUSES:
            raise ModuleError("status must be one of %s" % sorted(STATUSES))
        if "priority" in data and data["priority"] not in PRIORITIES:
            raise ModuleError("priority must be one of %s" % sorted(PRIORITIES))
        t.update({k: v for k, v in data.items()})
        t["updated_at"] = _now()
        if t["status"] == "done" and t.get("completed_at") is None:
            t["completed_at"] = t["updated_at"]
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "pm_task update")
        return {"status": "updated", "task": t, "tasks": [], "count": 1}

    if action == "complete":
        t = _task_or_raise(inputs.get("task_id"))
        if t["status"] == "done":
            raise ModuleError("task %r is already done" % t["id"])
        t["status"] = "done"
        t["updated_at"] = _now()
        t["completed_at"] = t["updated_at"]
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "pm_task complete")
        return {"status": "completed", "task": t, "tasks": [], "count": 1}

    if action == "reopen":
        t = _task_or_raise(inputs.get("task_id"))
        if t["status"] != "done":
            raise ModuleError("only done tasks can be reopened (current: %s)" % t["status"])
        t["status"] = "todo"
        t["completed_at"] = None
        t["updated_at"] = _now()
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "pm_task reopen")
        return {"status": "reopened", "task": t, "tasks": [], "count": 1}

    if action == "assign":
        t = _task_or_raise(inputs.get("task_id"))
        assignee = inputs.get("assignee")
        if not isinstance(assignee, str) or not assignee.strip():
            raise ModuleError("assignee must be a non-empty string")
        t["assignee"] = assignee.strip()
        t["updated_at"] = _now()
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "pm_task assign")
        return {"status": "assigned", "task": t, "tasks": [], "count": 1}

    if action == "add_subtask":
        t = _task_or_raise(inputs.get("task_id"))
        data = inputs.get("data")
        if not isinstance(data, dict):
            raise ModuleError("data must be an object for add_subtask")
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ModuleError("data.title is required for a subtask")
        sub = {
            "id": "sub_" + uuid.uuid4().hex[:8],
            "title": title.strip(),
            "done": False,
            "created_at": _now(),
        }
        t["subtasks"].append(sub)
        t["updated_at"] = _now()
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "pm_task add_subtask")
        return {"status": "subtask_added", "task": t, "tasks": [], "count": 1}

    # list
    status = inputs.get("status")
    if status is not None and status not in STATUSES:
        raise ModuleError("status filter must be one of %s" % sorted(STATUSES))
    project = inputs.get("project")
    limit = inputs.get("limit", 50)
    if not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ModuleError("limit must be an integer between 1 and 500")
    tasks = list(store.values())
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if project:
        tasks = [t for t in tasks if t.get("project") == project]
    tasks = sorted(tasks, key=lambda t: t.get("created_at", ""))[:limit]
    ctx.bill(EXEC_PRICE_USD, "pm_task list")
    return {"status": "ok", "task": {}, "tasks": tasks, "count": len(tasks)}
