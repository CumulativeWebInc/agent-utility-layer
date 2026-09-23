"""inventory_check — SKU inventory with reservations and reorder points.

Actions: add_sku / adjust / reserve / release / get / list / low_stock.
available = quantity_on_hand - reserved. Stock arithmetic is real and guarded:
adjustments may never drive on-hand negative; reservations may never exceed
available; releases may never exceed reserved. Nothing is fabricated —
unknown SKUs raise ModuleError. Store key: "aul:inventory_v1".
"""
from __future__ import annotations

EXEC_PRICE_USD = 0.001
STORE_KEY = "aul:inventory_v1"
ACTIONS = {"add_sku", "adjust", "reserve", "release", "get", "list", "low_stock"}


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


def _available(item: dict) -> int:
    return item["quantity_on_hand"] - item["reserved"]


def _with_available(item: dict) -> dict:
    out = dict(item)
    out["available"] = _available(item)
    return out


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError("invalid action %r; must be one of %s" % (action, sorted(ACTIONS)))

    store = _load(ctx)
    ctx.log("inventory_check.action", {"action": action})

    def _item_or_raise(sku):
        if not sku:
            raise ModuleError("sku is required")
        item = store.get(sku)
        if item is None:
            raise ModuleError("no inventory item found with sku %r" % sku)
        return item

    def _positive_int(value, what):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ModuleError("%s must be a positive integer, got %r" % (what, value))
        return value

    if action == "add_sku":
        data = inputs.get("data")
        if not isinstance(data, dict):
            raise ModuleError("data must be an object for add_sku")
        sku = data.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            raise ModuleError("data.sku is required (non-empty string)")
        sku = sku.strip()
        if sku in store:
            raise ModuleError("sku %r already exists; use adjust to change stock" % sku)
        name = data.get("name", "")
        if not isinstance(name, str):
            raise ModuleError("data.name must be a string")
        qoh = data.get("quantity_on_hand", 0)
        if not isinstance(qoh, int) or isinstance(qoh, bool) or qoh < 0:
            raise ModuleError("data.quantity_on_hand must be a non-negative integer")
        rop = data.get("reorder_point", 0)
        if not isinstance(rop, int) or isinstance(rop, bool) or rop < 0:
            raise ModuleError("data.reorder_point must be a non-negative integer")
        location = data.get("location", "")
        if not isinstance(location, str):
            raise ModuleError("data.location must be a string")
        item = {
            "sku": sku, "name": name.strip(), "quantity_on_hand": qoh,
            "reserved": 0, "reorder_point": rop, "location": location.strip(),
        }
        store[sku] = item
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "inventory_check add_sku")
        return {"status": "added", "item": _with_available(item), "items": [], "count": 1}

    if action == "adjust":
        item = _item_or_raise(inputs.get("sku"))
        delta = inputs.get("delta")
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise ModuleError("delta must be an integer, got %r" % (delta,))
        new_qoh = item["quantity_on_hand"] + delta
        if new_qoh < 0:
            raise ModuleError(
                "adjustment of %d would drive sku %r negative (on hand: %d)"
                % (delta, item["sku"], item["quantity_on_hand"]))
        if new_qoh < item["reserved"]:
            raise ModuleError(
                "adjustment would leave on-hand (%d) below reserved (%d) for sku %r"
                % (new_qoh, item["reserved"], item["sku"]))
        item["quantity_on_hand"] = new_qoh
        store[item["sku"]] = item
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "inventory_check adjust")
        return {"status": "adjusted", "item": _with_available(item), "items": [], "count": 1}

    if action == "reserve":
        item = _item_or_raise(inputs.get("sku"))
        qty = _positive_int(inputs.get("quantity"), "quantity")
        if qty > _available(item):
            raise ModuleError(
                "cannot reserve %d of sku %r: only %d available"
                % (qty, item["sku"], _available(item)))
        item["reserved"] += qty
        store[item["sku"]] = item
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "inventory_check reserve")
        return {"status": "reserved", "item": _with_available(item), "items": [], "count": 1}

    if action == "release":
        item = _item_or_raise(inputs.get("sku"))
        qty = _positive_int(inputs.get("quantity"), "quantity")
        if qty > item["reserved"]:
            raise ModuleError(
                "cannot release %d of sku %r: only %d reserved"
                % (qty, item["sku"], item["reserved"]))
        item["reserved"] -= qty
        store[item["sku"]] = item
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "inventory_check release")
        return {"status": "released", "item": _with_available(item), "items": [], "count": 1}

    if action == "get":
        item = _item_or_raise(inputs.get("sku"))
        ctx.bill(EXEC_PRICE_USD, "inventory_check get")
        return {"status": "ok", "item": _with_available(item), "items": [], "count": 1}

    if action == "list":
        limit = inputs.get("limit", 50)
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ModuleError("limit must be an integer between 1 and 500")
        items = [_with_available(i) for i in sorted(store.values(), key=lambda x: x["sku"])][:limit]
        ctx.bill(EXEC_PRICE_USD, "inventory_check list")
        return {"status": "ok", "item": {}, "items": items, "count": len(items)}

    # low_stock
    items = [_with_available(i) for i in store.values()
             if i["quantity_on_hand"] <= i["reorder_point"]]
    items = sorted(items, key=lambda x: x["sku"])
    ctx.bill(EXEC_PRICE_USD, "inventory_check low_stock")
    return {"status": "ok", "item": {}, "items": items, "count": len(items)}
