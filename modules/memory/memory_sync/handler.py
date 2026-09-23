"""memory_sync — POST /v1/memory/sync: store/retrieve cross-session user memory.

Real logic, $0: each user's memory is a JSON dict stored via ctx.memory under
the scoped key "aul:memory_sync_v1" (dict user_id -> dict). Retrieve returns
ONLY what was previously stored through store() — nothing is fabricated.
"""
from __future__ import annotations

import json

EXEC_PRICE_USD = 0.001
STORE_KEY = "aul:memory_sync_v1"
ACTIONS = {"store", "retrieve"}
MAX_KEYS_PER_STORE = 200
MAX_VALUE_CHARS = 20_000


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _load(ctx) -> dict:
    store = ctx.memory_get(STORE_KEY)
    return dict(store) if isinstance(store, dict) else {}


def _save(ctx, store: dict) -> None:
    ctx.memory_set(STORE_KEY, store)


def _check_jsonable(value) -> None:
    try:
        text = json.dumps(value)
    except (TypeError, ValueError) as e:
        raise ModuleError("memory values must be JSON-serializable: %s" % e)
    if len(text) > MAX_VALUE_CHARS:
        raise ModuleError("memory value exceeds %d chars" % MAX_VALUE_CHARS)


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. Returns a dict matching outputs_schema."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    user_id = inputs.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ModuleError("user_id is required and must be a non-empty string")

    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError(
            "invalid action %r; must be one of %s" % (action, sorted(ACTIONS))
        )

    store = _load(ctx)
    user_mem = store.get(user_id)
    if not isinstance(user_mem, dict):
        user_mem = {}

    ctx.log("memory_sync.action", {"user_id": user_id, "action": action})

    if action == "store":
        new_memory = inputs.get("new_memory")
        if not isinstance(new_memory, dict) or not new_memory:
            raise ModuleError("new_memory must be a non-empty object for store")
        if len(new_memory) > MAX_KEYS_PER_STORE:
            raise ModuleError("store limited to %d keys per call" % MAX_KEYS_PER_STORE)
        for k, v in new_memory.items():
            if not isinstance(k, str) or not k:
                raise ModuleError("memory keys must be non-empty strings")
            _check_jsonable(v)
        stored_keys = []
        for k, v in new_memory.items():
            user_mem[k] = v
            stored_keys.append(k)
        store[user_id] = user_mem
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "memory_sync store")
        return {
            "status": "success",
            "user_id": user_id,
            "memories": dict(user_mem),
            "stored_keys": stored_keys,
        }

    # retrieve
    context_keys = inputs.get("context_keys")
    if context_keys is not None:
        if not isinstance(context_keys, list) or not all(
            isinstance(k, str) for k in context_keys
        ):
            raise ModuleError("context_keys must be a list of strings when provided")
        memories = {k: user_mem[k] for k in context_keys if k in user_mem}
    else:
        memories = dict(user_mem)
    ctx.bill(EXEC_PRICE_USD, "memory_sync retrieve")
    return {"status": "success", "user_id": user_id, "memories": memories}
