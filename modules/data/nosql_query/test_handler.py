"""Tests for nosql_query handler."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handler import ApprovalDenied, ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self, approve=True):
        self._approve = approve
        self.store = {}
        self.logs = []
        self.approvals = []

    def auth_get(self, provider):
        raise AssertionError("no provider needed")

    def approval_request(self, summary, timeout_seconds=300):
        self.approvals.append(summary)
        if not self._approve:
            raise ApprovalDenied("human said no")
        return "appr_fake_1"

    def memory_get(self, key):
        return self.store.get(key)

    def memory_set(self, key, value):
        self.store[key] = value

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        pass


def seed(ctx):
    for doc in [{"name": "a", "n": 1}, {"name": "b", "n": 2}, {"name": "c", "n": 3}]:
        execute({"operation": "insert", "collection": "items", "document": doc}, ctx)


def test_insert_and_find():
    ctx = FakeCtx()
    out = execute({"operation": "insert", "collection": "items",
                   "document": {"name": "x"}}, ctx)
    assert out["status"] == "ok" and out["modified"] == 1
    assert "_id" in out["docs"][0]
    found = execute({"operation": "find", "collection": "items",
                     "filter": {"name": "x"}}, ctx)
    assert found["matched"] == 1
    assert found["docs"][0]["name"] == "x"


def test_filter_operators():
    ctx = FakeCtx()
    seed(ctx)
    out = execute({"operation": "find", "collection": "items",
                   "filter": {"n": {"$gt": 1}}}, ctx)
    assert out["matched"] == 2
    out = execute({"operation": "find", "collection": "items",
                   "filter": {"n": {"$in": [1, 3]}}}, ctx)
    assert out["matched"] == 2
    out = execute({"operation": "find", "collection": "items",
                   "filter": {"name": {"$contains": "b"}}}, ctx)
    assert out["matched"] == 1
    out = execute({"operation": "find", "collection": "items",
                   "filter": {"n": {"$lte": 1}}}, ctx)
    assert out["matched"] == 1
    try:
        execute({"operation": "find", "collection": "items",
                 "filter": {"n": {"$bogus": 1}}}, ctx)
        raise AssertionError("expected ModuleError")
    except ModuleError:
        pass


def test_update_and_count():
    ctx = FakeCtx()
    seed(ctx)
    out = execute({"operation": "update", "collection": "items",
                   "filter": {"name": "a"}, "update": {"n": 10}}, ctx)
    assert out["modified"] == 1
    found = execute({"operation": "find", "collection": "items",
                     "filter": {"name": "a"}}, ctx)
    assert found["docs"][0]["n"] == 10
    assert "_id" in found["docs"][0]  # _id preserved
    cnt = execute({"operation": "count", "collection": "items",
                   "filter": {"n": {"$gte": 2}}}, ctx)
    assert cnt["matched"] == 3  # a(n=10), b(n=2), c(n=3)


def test_delete_requires_approval_and_applies():
    ctx = FakeCtx(approve=True)
    seed(ctx)
    out = execute({"operation": "delete", "collection": "items",
                   "filter": {"n": {"$gt": 1}}}, ctx)
    assert out["modified"] == 2
    assert ctx.approvals
    left = execute({"operation": "count", "collection": "items"}, ctx)
    assert left["matched"] == 1


def test_delete_denied_raises_and_keeps_data():
    ctx = FakeCtx(approve=False)
    seed(ctx)
    try:
        execute({"operation": "delete", "collection": "items", "filter": {}}, ctx)
        raise AssertionError("expected ApprovalDenied")
    except ApprovalDenied:
        pass
    left = execute({"operation": "count", "collection": "items"}, ctx)
    assert left["matched"] == 3  # nothing deleted


def test_drop_requires_approval():
    ctx = FakeCtx(approve=True)
    seed(ctx)
    out = execute({"operation": "drop", "collection": "items"}, ctx)
    assert out["status"] == "ok" and out["matched"] == 3
    cols = execute({"operation": "list_collections"}, ctx)
    assert cols["docs"] == []
    ctx2 = FakeCtx(approve=False)
    seed(ctx2)
    try:
        execute({"operation": "drop", "collection": "items"}, ctx2)
        raise AssertionError("expected ApprovalDenied")
    except ApprovalDenied:
        pass


def test_list_collections_and_find_limit():
    ctx = FakeCtx()
    seed(ctx)
    execute({"operation": "insert", "collection": "other", "document": {}}, ctx)
    out = execute({"operation": "list_collections"}, ctx)
    assert {d["name"] for d in out["docs"]} == {"items", "other"}
    out2 = execute({"operation": "find", "collection": "items", "limit": 2}, ctx)
    assert len(out2["docs"]) == 2 and out2["matched"] == 3


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    cases = [
        {"operation": "frobnicate"},
        {"operation": "find"},  # no collection
        {"operation": "find", "collection": ""},
        {"operation": "insert", "collection": "c"},  # no document
        {"operation": "insert", "collection": "c", "document": []},
        {"operation": "update", "collection": "c",
         "filter": {}, "update": {}},
        {"operation": "find", "collection": "c", "filter": []},
        {"operation": "find", "collection": "c", "limit": 0},
        {"operation": "count", "collection": "c", "limit": "x"},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:50]!r}")
        except ModuleError:
            pass


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute({"operation": "insert", "collection": "c",
                   "document": {"a": 1}}, ctx)
    assert set(out.keys()) == {
        "status", "operation", "collection", "matched", "modified", "docs"
    }
