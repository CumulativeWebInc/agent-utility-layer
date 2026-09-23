"""Tests for data_transform handler."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handler import ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self):
        self.logs = []

    def auth_get(self, provider):
        raise AssertionError("no provider needed")

    def approval_request(self, summary, timeout_seconds=300):
        raise AssertionError("no approval needed")

    def memory_get(self, key):
        return None

    def memory_set(self, key, value):
        pass

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        pass


DATA = [
    {"name": "a", "dept": "x", "n": 1, "tags": {"k": "v1"}},
    {"name": "b", "dept": "y", "n": 2, "tags": {"k": "v2"}},
    {"name": "c", "dept": "x", "n": 3, "tags": {"k": "v3"}},
]


def run(data, pipeline):
    return execute({"data": data, "pipeline": pipeline}, FakeCtx())


def test_filter_select_sort_limit_chain():
    out = run(DATA, [
        {"op": "filter", "where": {"n": {"$gte": 2}}},
        {"op": "select", "fields": ["name", "n"]},
        {"op": "sort", "by": "n", "desc": True},
        {"op": "limit", "n": 1},
    ])
    assert out["status"] == "ok"
    assert out["rows"] == [{"name": "c", "n": 3}]
    assert out["row_count"] == 1
    assert out["ops_applied"] == ["filter", "select", "sort", "limit"]


def test_filter_operators():
    out = run(DATA, [{"op": "filter", "where": {"dept": "x"}}])
    assert out["row_count"] == 2
    out = run(DATA, [{"op": "filter", "where": {"name": {"$in": ["a", "c"]}}}])
    assert out["row_count"] == 2
    out = run(DATA, [{"op": "filter", "where": {"name": {"$contains": "b"}}}])
    assert out["row_count"] == 1
    out = run(DATA, [{"op": "filter", "where": {"n": {"$lt": 2, "$gt": 0}}}])
    assert out["row_count"] == 1


def test_rename_and_flatten():
    out = run(DATA, [
        {"op": "rename", "mapping": {"name": "label"}},
        {"op": "flatten"},
    ])
    assert out["rows"][0]["label"] == "a"
    assert out["rows"][0]["tags.k"] == "v1"
    assert "tags" not in out["rows"][0]


def test_group_by_aggs():
    out = run(DATA, [
        {"op": "group_by", "field": "dept", "aggs": [
            {"fn": "count", "as": "cnt"},
            {"fn": "sum", "field": "n", "as": "total"},
            {"fn": "avg", "field": "n", "as": "mean"},
            {"fn": "max", "field": "n", "as": "mx"},
            {"fn": "min", "field": "n", "as": "mn"},
        ]},
        {"op": "sort", "by": "dept"},
    ])
    assert out["row_count"] == 2
    x = [r for r in out["rows"] if r["dept"] == "x"][0]
    assert x == {"dept": "x", "cnt": 2, "total": 4, "mean": 2.0, "mx": 3, "mn": 1}


def test_group_by_non_numeric_rejected():
    try:
        run(DATA, [{"op": "group_by", "field": "dept",
                    "aggs": [{"fn": "sum", "field": "name", "as": "s"}]}])
        raise AssertionError("expected ModuleError")
    except ModuleError:
        pass


def test_empty_result_is_fine():
    out = run(DATA, [{"op": "filter", "where": {"n": {"$gt": 100}}}])
    assert out["status"] == "ok" and out["rows"] == [] and out["row_count"] == 0


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    cases = [
        {"data": DATA, "pipeline": [{"op": "frobnicate"}]},
        {"data": DATA, "pipeline": [{"op": "filter"}]},  # no where
        {"data": DATA, "pipeline": [{"op": "filter", "where": {"n": {"$x": 1}}}]},
        {"data": DATA, "pipeline": [{"op": "select", "fields": []}]},
        {"data": DATA, "pipeline": [{"op": "rename", "mapping": {}}]},
        {"data": DATA, "pipeline": [{"op": "sort"}]},
        {"data": DATA, "pipeline": [{"op": "limit", "n": -1}]},
        {"data": DATA, "pipeline": [{"op": "group_by", "field": "dept",
                                     "aggs": []}]},
        {"data": DATA, "pipeline": []},
        {"data": DATA, "pipeline": "nope"},
        {"data": [1, 2], "pipeline": [{"op": "limit", "n": 1}]},
        {"data": DATA},
        {"pipeline": [{"op": "limit", "n": 1}]},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:50]!r}")
        except ModuleError:
            pass


def test_input_not_mutated():
    import copy
    snapshot = copy.deepcopy(DATA)
    run(DATA, [{"op": "rename", "mapping": {"name": "z"}},
               {"op": "flatten"}])
    assert DATA == snapshot


def test_outputs_match_schema_keys():
    out = run(DATA, [{"op": "limit", "n": 2}])
    assert set(out.keys()) == {"status", "rows", "row_count", "ops_applied"}
