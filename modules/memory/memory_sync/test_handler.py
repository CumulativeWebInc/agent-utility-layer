"""Tests for memory_sync. FakeCtx = in-memory stand-in for the spine ctx;
fake providers are clearly labeled and never presented as live."""
import json
import os
import sys

import pytest

from . import handler


class FakeCtx:
    """Duck-typed spine ctx for tests. FAKE — demo only."""

    def __init__(self):
        self.mem = {}
        self.bills = []
        self.logs = []

    def auth_get(self, provider):
        raise handler.AuthMissing("no credential configured for '%s'" % provider)

    def approval_request(self, summary, timeout_seconds=300):
        return "appr_test"

    def memory_get(self, key):
        return self.mem.get(key)

    def memory_set(self, key, value):
        self.mem[key] = value

    def log(self, event, data=None):
        self.logs.append((event, dict(data or {})))

    def bill(self, amount_usd, memo):
        self.bills.append({"amount_usd": amount_usd, "memo": memo})


def test_store_happy_path():
    ctx = FakeCtx()
    out = handler.execute(
        {"user_id": "usr_991823", "action": "store",
         "new_memory": {"preferred_currency": "USD", "dietary_restrictions": "vegan"}},
        ctx,
    )
    assert out["status"] == "success"
    assert out["user_id"] == "usr_991823"
    assert out["memories"]["preferred_currency"] == "USD"
    assert sorted(out["stored_keys"]) == ["dietary_restrictions", "preferred_currency"]
    assert ctx.bills and ctx.bills[0]["amount_usd"] == 0.001


def test_retrieve_full_and_subset():
    ctx = FakeCtx()
    handler.execute(
        {"user_id": "u1", "action": "store",
         "new_memory": {"a": 1, "b": 2, "c": 3}},
        ctx,
    )
    out = handler.execute({"user_id": "u1", "action": "retrieve"}, ctx)
    assert out["memories"] == {"a": 1, "b": 2, "c": 3}
    out2 = handler.execute(
        {"user_id": "u1", "action": "retrieve", "context_keys": ["a", "missing_key"]},
        ctx,
    )
    assert out2["memories"] == {"a": 1}


def test_store_merges_not_replaces():
    ctx = FakeCtx()
    handler.execute({"user_id": "u2", "action": "store", "new_memory": {"a": 1}}, ctx)
    out = handler.execute(
        {"user_id": "u2", "action": "store", "new_memory": {"b": 2}}, ctx
    )
    assert out["memories"] == {"a": 1, "b": 2}


def test_retrieve_unknown_user_returns_empty():
    ctx = FakeCtx()
    out = handler.execute({"user_id": "nobody", "action": "retrieve"}, ctx)
    assert out["status"] == "success"
    assert out["memories"] == {}


def test_invalid_action_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute({"user_id": "u", "action": "delete"}, ctx)


def test_store_requires_new_memory():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute({"user_id": "u", "action": "store"}, ctx)
    with pytest.raises(handler.ModuleError):
        handler.execute({"user_id": "u", "action": "store", "new_memory": {}}, ctx)


def test_non_jsonable_value_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute(
            {"user_id": "u", "action": "store", "new_memory": {"bad": object()}},
            ctx,
        )


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute({"user_id": "", "action": "retrieve"}, ctx)
    with pytest.raises(handler.ModuleError):
        handler.execute({"action": "retrieve"}, ctx)  # missing user_id
    with pytest.raises(handler.ModuleError):
        handler.execute(
            {"user_id": "u", "action": "retrieve", "context_keys": "a,b"}, ctx
        )


def test_outputs_match_schema_keys():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "capability.json")) as f:
        schema = json.load(f)["outputs_schema"]["properties"]
    ctx = FakeCtx()
    out = handler.execute(
        {"user_id": "u", "action": "store", "new_memory": {"k": "v"}}, ctx
    )
    for k in ("status", "user_id", "memories"):
        assert k in out and k in schema
