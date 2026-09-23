"""pytest for inventory_check — guarded stock arithmetic verified."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def _add(ctx, **over):
    data = {"sku": "CWI-1", "name": "Signal Boy", "quantity_on_hand": 100,
            "reorder_point": 20, "location": "warehouse-A"}
    data.update(over)
    return handler.execute({"action": "add_sku", "data": data}, ctx)["item"]


def test_add_and_get_happy_path():
    ctx = make_ctx()
    item = _add(ctx)
    assert item["sku"] == "CWI-1" and item["available"] == 100
    got = handler.execute({"action": "get", "sku": "CWI-1"}, ctx)
    assert set(got.keys()) == {"status", "item", "items", "count"}
    assert got["item"]["quantity_on_hand"] == 100


def test_duplicate_sku_rejected():
    ctx = make_ctx()
    _add(ctx)
    try:
        _add(ctx)
    except handler.ModuleError as e:
        assert "already exists" in str(e)
    else:
        raise AssertionError("expected ModuleError for duplicate sku")


def test_reserve_release_math():
    ctx = make_ctx()
    _add(ctx)
    r = handler.execute({"action": "reserve", "sku": "CWI-1", "quantity": 30}, ctx)
    assert r["item"]["reserved"] == 30 and r["item"]["available"] == 70
    rel = handler.execute({"action": "release", "sku": "CWI-1", "quantity": 10}, ctx)
    assert rel["item"]["reserved"] == 20 and rel["item"]["available"] == 80


def test_reserve_more_than_available_rejected():
    ctx = make_ctx()
    _add(ctx)
    try:
        handler.execute({"action": "reserve", "sku": "CWI-1", "quantity": 101}, ctx)
    except handler.ModuleError as e:
        assert "available" in str(e)
    else:
        raise AssertionError("expected ModuleError over-reserving")
    # stock untouched
    assert handler.execute({"action": "get", "sku": "CWI-1"}, ctx)["item"]["available"] == 100


def test_release_more_than_reserved_rejected():
    ctx = make_ctx()
    _add(ctx)
    try:
        handler.execute({"action": "release", "sku": "CWI-1", "quantity": 5}, ctx)
    except handler.ModuleError as e:
        assert "reserved" in str(e)
    else:
        raise AssertionError("expected ModuleError over-releasing")


def test_adjust_negative_below_zero_rejected():
    ctx = make_ctx()
    _add(ctx)
    try:
        handler.execute({"action": "adjust", "sku": "CWI-1", "delta": -101}, ctx)
    except handler.ModuleError as e:
        assert "negative" in str(e)
    else:
        raise AssertionError("expected ModuleError driving stock negative")
    ok = handler.execute({"action": "adjust", "sku": "CWI-1", "delta": -40}, ctx)
    assert ok["item"]["quantity_on_hand"] == 60


def test_adjust_below_reserved_rejected():
    ctx = make_ctx()
    _add(ctx)
    handler.execute({"action": "reserve", "sku": "CWI-1", "quantity": 90}, ctx)
    try:
        handler.execute({"action": "adjust", "sku": "CWI-1", "delta": -20}, ctx)
    except handler.ModuleError as e:
        assert "reserved" in str(e)
    else:
        raise AssertionError("expected ModuleError cutting below reserved")


def test_low_stock_report():
    ctx = make_ctx()
    _add(ctx)
    handler.execute({"action": "add_sku", "data": {
        "sku": "CWI-2", "name": "Crown Cap", "quantity_on_hand": 5,
        "reorder_point": 20}}, ctx)
    res = handler.execute({"action": "low_stock"}, ctx)
    assert res["count"] == 1
    assert res["items"][0]["sku"] == "CWI-2"


def test_get_unknown_sku_never_fabricates():
    ctx = make_ctx()
    try:
        handler.execute({"action": "get", "sku": "NOPE-9"}, ctx)
    except handler.ModuleError as e:
        assert "no inventory item" in str(e)
    else:
        raise AssertionError("expected ModuleError")
