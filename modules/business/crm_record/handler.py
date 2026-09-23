"""crm_record — CRUD over CRM records (contact/company/deal/lead).

Store: JSON-backed via ctx.memory, scoped key "aul:crm_records_v1".
No external provider; nothing is ever fabricated — every record returned
was previously written through create().
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

EXEC_PRICE_USD = 0.001
STORE_KEY = "aul:crm_records_v1"

ACTIONS = {"create", "get", "update", "delete", "list", "search"}
RECORD_TYPES = {"contact", "company", "deal", "lead"}


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


def _new_id() -> str:
    return "rec_" + uuid.uuid4().hex[:12]


def _searchable(record: dict) -> str:
    parts = []
    for k in ("name", "email", "company", "title", "phone", "notes"):
        v = record.get(k)
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. Returns a dict matching outputs_schema."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError(
            "invalid action %r; must be one of %s" % (action, sorted(ACTIONS))
        )

    store = _load(ctx)
    ctx.log("crm_record.action", {"action": action})

    if action == "create":
        record_type = inputs.get("record_type")
        if record_type not in RECORD_TYPES:
            raise ModuleError(
                "record_type is required and must be one of %s" % sorted(RECORD_TYPES)
            )
        data = inputs.get("data")
        if not isinstance(data, dict) or not data:
            raise ModuleError("data must be a non-empty object for create")
        rid = _new_id()
        record = {
            "id": rid,
            "record_type": record_type,
            "created_at": _now(),
            "updated_at": _now(),
        }
        record.update(data)
        store[rid] = record
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "crm_record create")
        return {"status": "created", "record": record, "records": [], "count": 1}

    if action == "get":
        rid = inputs.get("record_id")
        if not rid:
            raise ModuleError("record_id is required for get")
        record = store.get(rid)
        if record is None:
            raise ModuleError("no CRM record found with id %r" % rid)
        ctx.bill(EXEC_PRICE_USD, "crm_record get")
        return {"status": "ok", "record": record, "records": [], "count": 1}

    if action == "update":
        rid = inputs.get("record_id")
        if not rid:
            raise ModuleError("record_id is required for update")
        record = store.get(rid)
        if record is None:
            raise ModuleError("no CRM record found with id %r" % rid)
        data = inputs.get("data")
        if not isinstance(data, dict) or not data:
            raise ModuleError("data must be a non-empty object for update")
        data = dict(data)
        data.pop("id", None)
        data.pop("created_at", None)
        record.update(data)
        record["updated_at"] = _now()
        store[rid] = record
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "crm_record update")
        return {"status": "updated", "record": record, "records": [], "count": 1}

    if action == "delete":
        rid = inputs.get("record_id")
        if not rid:
            raise ModuleError("record_id is required for delete")
        if rid not in store:
            raise ModuleError("no CRM record found with id %r" % rid)
        del store[rid]
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "crm_record delete")
        return {"status": "deleted", "record": {}, "records": [], "count": 0}

    if action == "list":
        record_type = inputs.get("record_type")
        limit = inputs.get("limit", 50)
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ModuleError("limit must be an integer between 1 and 500")
        records = list(store.values())
        if record_type is not None:
            if record_type not in RECORD_TYPES:
                raise ModuleError("record_type must be one of %s" % sorted(RECORD_TYPES))
            records = [r for r in records if r.get("record_type") == record_type]
        records = sorted(records, key=lambda r: r.get("created_at", ""))[:limit]
        ctx.bill(EXEC_PRICE_USD, "crm_record list")
        return {"status": "ok", "record": {}, "records": records, "count": len(records)}

    # action == "search"
    query = inputs.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ModuleError("query must be a non-empty string for search")
    limit = inputs.get("limit", 50)
    if not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ModuleError("limit must be an integer between 1 and 500")
    needle = query.strip().lower()
    hits = [r for r in store.values() if needle in _searchable(r)]
    hits = sorted(hits, key=lambda r: r.get("created_at", ""))[:limit]
    ctx.bill(EXEC_PRICE_USD, "crm_record search")
    return {"status": "ok", "record": {}, "records": hits, "count": len(hits)}
