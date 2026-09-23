"""helpdesk_ticket — ticket lifecycle in a JSON-backed store.

Actions: create / get / update / add_comment / assign / close / reopen / list.
Statuses: open -> in_progress -> pending -> resolved -> closed.
Store key: "aul:tickets_v1". No external provider; nothing fabricated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

EXEC_PRICE_USD = 0.001
STORE_KEY = "aul:tickets_v1"

ACTIONS = {"create", "get", "update", "add_comment", "assign", "close", "reopen", "list"}
STATUSES = {"open", "in_progress", "pending", "resolved", "closed"}
PRIORITIES = {"low", "medium", "high", "urgent"}
UPDATE_FIELDS = {"title", "description", "priority", "status", "assignee"}


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
    ctx.log("helpdesk_ticket.action", {"action": action})

    def _ticket_or_raise(tid):
        if not tid:
            raise ModuleError("ticket_id is required")
        t = store.get(tid)
        if t is None:
            raise ModuleError("no ticket found with id %r" % tid)
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
        tid = "tkt_" + uuid.uuid4().hex[:12]
        ticket = {
            "id": tid,
            "title": title.strip(),
            "description": data.get("description", ""),
            "requester": data.get("requester", ""),
            "priority": priority,
            "status": "open",
            "assignee": data.get("assignee", ""),
            "comments": [],
            "created_at": _now(),
            "updated_at": _now(),
            "resolved_at": None,
        }
        store[tid] = ticket
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket create")
        return {"status": "created", "ticket": ticket, "tickets": [], "count": 1}

    if action == "get":
        t = _ticket_or_raise(inputs.get("ticket_id"))
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket get")
        return {"status": "ok", "ticket": t, "tickets": [], "count": 1}

    if action == "update":
        t = _ticket_or_raise(inputs.get("ticket_id"))
        data = inputs.get("data")
        if not isinstance(data, dict) or not data:
            raise ModuleError("data must be a non-empty object for update")
        for k in data:
            if k not in UPDATE_FIELDS:
                raise ModuleError("cannot update field %r; allowed: %s"
                                  % (k, sorted(UPDATE_FIELDS)))
        if "priority" in data and data["priority"] not in PRIORITIES:
            raise ModuleError("priority must be one of %s" % sorted(PRIORITIES))
        if "status" in data and data["status"] not in STATUSES:
            raise ModuleError("status must be one of %s" % sorted(STATUSES))
        t.update({k: v for k, v in data.items()})
        t["updated_at"] = _now()
        if t["status"] in ("resolved", "closed") and t.get("resolved_at") is None:
            t["resolved_at"] = t["updated_at"]
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket update")
        return {"status": "updated", "ticket": t, "tickets": [], "count": 1}

    if action == "add_comment":
        t = _ticket_or_raise(inputs.get("ticket_id"))
        comment = inputs.get("comment")
        if not isinstance(comment, str) or not comment.strip():
            raise ModuleError("comment must be a non-empty string")
        t["comments"].append({
            "author": inputs.get("data", {}).get("author", "") if isinstance(inputs.get("data"), dict) else "",
            "body": comment.strip(),
            "created_at": _now(),
        })
        t["updated_at"] = _now()
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket add_comment")
        return {"status": "commented", "ticket": t, "tickets": [], "count": 1}

    if action == "assign":
        t = _ticket_or_raise(inputs.get("ticket_id"))
        assignee = inputs.get("assignee")
        if not isinstance(assignee, str) or not assignee.strip():
            raise ModuleError("assignee must be a non-empty string")
        t["assignee"] = assignee.strip()
        t["updated_at"] = _now()
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket assign")
        return {"status": "assigned", "ticket": t, "tickets": [], "count": 1}

    if action == "close":
        t = _ticket_or_raise(inputs.get("ticket_id"))
        t["status"] = "closed"
        t["updated_at"] = _now()
        t["resolved_at"] = t["resolved_at"] or t["updated_at"]
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket close")
        return {"status": "closed", "ticket": t, "tickets": [], "count": 1}

    if action == "reopen":
        t = _ticket_or_raise(inputs.get("ticket_id"))
        if t["status"] not in ("resolved", "closed"):
            raise ModuleError("only resolved/closed tickets can be reopened (current: %s)" % t["status"])
        t["status"] = "open"
        t["updated_at"] = _now()
        store[t["id"]] = t
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket reopen")
        return {"status": "reopened", "ticket": t, "tickets": [], "count": 1}

    # list
    status = inputs.get("status")
    if status is not None and status not in STATUSES:
        raise ModuleError("status filter must be one of %s" % sorted(STATUSES))
    limit = inputs.get("limit", 50)
    if not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ModuleError("limit must be an integer between 1 and 500")
    tickets = list(store.values())
    if status:
        tickets = [t for t in tickets if t["status"] == status]
    tickets = sorted(tickets, key=lambda t: t.get("created_at", ""))[:limit]
    ctx.bill(EXEC_PRICE_USD, "helpdesk_ticket list")
    return {"status": "ok", "ticket": {}, "tickets": tickets, "count": len(tickets)}
