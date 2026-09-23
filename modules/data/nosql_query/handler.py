"""nosql_query — real JSON document store backed by ctx scoped memory.

CRUD over named collections. Filters support $eq/$ne/$gt/$gte/$lt/$lte/$in/
$contains. delete/drop are destructive and require ctx.approval_request first.
"""

import uuid


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_STORE_KEY = "nosql:store"
_NEEDS_COLLECTION = ("insert", "find", "update", "delete", "drop", "count")
_OPS_REQUIRING_APPROVAL = ("delete", "drop")

_OPS = {
    "$eq": lambda a, b: a == b,
    "$ne": lambda a, b: a != b,
    "$gt": lambda a, b: a is not None and b is not None and a > b,
    "$gte": lambda a, b: a is not None and b is not None and a >= b,
    "$lt": lambda a, b: a is not None and b is not None and a < b,
    "$lte": lambda a, b: a is not None and b is not None and a <= b,
    "$in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
    "$contains": lambda a, b: isinstance(a, str) and b in a,
}


def _matches(doc: dict, filt: dict) -> bool:
    for field, cond in filt.items():
        val = doc.get(field)
        if isinstance(cond, dict) and cond and all(
            k.startswith("$") for k in cond
        ):
            for op, operand in cond.items():
                if op not in _OPS:
                    raise ModuleError(f"unknown filter operator '{op}'")
                try:
                    if not _OPS[op](val, operand):
                        return False
                except TypeError:
                    return False
        else:
            if val != cond:
                return False
    return True


def _load(ctx) -> dict:
    store = ctx.memory_get(_STORE_KEY)
    if store is None:
        return {}
    if not isinstance(store, dict):
        raise ModuleError("nosql store in memory is corrupt (not a dict)")
    return store


def _save(ctx, store: dict):
    ctx.memory_set(_STORE_KEY, store)


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    op = inputs.get("operation")
    if op not in ("insert", "find", "update", "delete", "drop", "count",
                  "list_collections"):
        raise ModuleError(
            "input 'operation' must be one of: insert, find, update, delete, "
            "drop, count, list_collections"
        )
    collection = inputs.get("collection")
    if op in _NEEDS_COLLECTION:
        if not isinstance(collection, str) or not collection.strip():
            raise ModuleError(
                f"input 'collection' (non-empty string) is required for '{op}'"
            )
        collection = collection.strip()
    limit = inputs.get("limit", 100)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ModuleError("input 'limit' must be a positive integer")

    filt = inputs.get("filter", {})
    if not isinstance(filt, dict):
        raise ModuleError("input 'filter' must be an object")

    if op in _OPS_REQUIRING_APPROVAL:
        # Destructive actions REQUIRE human approval first.
        scope = f"collection '{collection}'" if op == "delete" else f"collection '{collection}' (drop entire collection)"
        ctx.approval_request(
            f"nosql_query {op} on {scope} matching {filt}", timeout_seconds=300
        )

    store = _load(ctx)
    docs_out, matched, modified = [], 0, 0

    if op == "list_collections":
        return {"status": "ok", "operation": op, "collection": "",
                "matched": len(store), "modified": 0,
                "docs": [{"name": k} for k in sorted(store)]}

    coll = store.get(collection, [])
    if op == "insert":
        doc = inputs.get("document")
        if not isinstance(doc, dict):
            raise ModuleError("input 'document' (object) is required for 'insert'")
        new_doc = dict(doc)
        new_doc.setdefault("_id", uuid.uuid4().hex)
        coll.append(new_doc)
        store[collection] = coll
        _save(ctx, store)
        docs_out, matched, modified = [new_doc], 1, 1
    elif op == "find":
        matched_docs = [d for d in coll if _matches(d, filt)]
        matched = len(matched_docs)
        docs_out = matched_docs[:limit]
    elif op == "count":
        matched = sum(1 for d in coll if _matches(d, filt))
    elif op == "update":
        update = inputs.get("update")
        if not isinstance(update, dict) or not update:
            raise ModuleError("input 'update' (non-empty object) is required for 'update'")
        new_coll = []
        for d in coll:
            if _matches(d, filt):
                merged = dict(d)
                merged.update(update)
                merged["_id"] = d.get("_id")
                new_coll.append(merged)
                modified += 1
            else:
                new_coll.append(d)
        matched = modified
        store[collection] = new_coll
        _save(ctx, store)
    elif op == "delete":
        kept = [d for d in coll if not _matches(d, filt)]
        matched = modified = len(coll) - len(kept)
        store[collection] = kept
        _save(ctx, store)
    elif op == "drop":
        matched = len(coll)
        store.pop(collection, None)
        _save(ctx, store)

    ctx.log("nosql_query", {"op": op, "collection": collection,
                            "matched": matched, "modified": modified})
    return {
        "status": "ok",
        "operation": op,
        "collection": collection or "",
        "matched": matched,
        "modified": modified,
        "docs": docs_out,
    }
