"""Tests for mem_long_term."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_mem_long_term", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_remember_recall(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "remember", "namespace": "user", "key": "name",
             "value": "Black", "importance": 0.9, "tags": ["identity"]}, ctx)
    r = execute({"op": "recall", "namespace": "user", "key": "name"}, ctx)
    assert r["found"] is True and r["value"] == "Black"
    assert r["importance"] == 0.9 and r["tags"] == ["identity"]


def test_recall_missing(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "recall", "namespace": "user", "key": "nope"}, ctx)
    assert r["found"] is False


def test_query_tag_and_importance(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "remember", "namespace": "n", "key": "a", "value": 1,
             "importance": 0.9, "tags": ["x"]}, ctx)
    execute({"op": "remember", "namespace": "n", "key": "b", "value": 2,
             "importance": 0.2, "tags": ["y"]}, ctx)
    q = execute({"op": "query", "namespace": "n", "min_importance": 0.5}, ctx)
    assert [e["key"] for e in q["entries"]] == ["a"]
    q2 = execute({"op": "query", "namespace": "n", "tag": "y"}, ctx)
    assert [e["key"] for e in q2["entries"]] == ["b"]


def test_forget_and_namespaces(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "remember", "namespace": "n", "key": "a", "value": 1}, ctx)
    d = execute({"op": "forget", "namespace": "n", "key": "a"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "recall", "namespace": "n", "key": "a"}, ctx)["found"] is False
    ns = execute({"op": "namespaces"}, ctx)
    assert ns["namespaces"] == []


def test_invalid_importance_and_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "remember", "namespace": "n", "key": "a", "value": 1,
                 "importance": 2.0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "remember", "namespace": "n", "key": "a", "value": 1,
                 "tags": "notalist"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)


def test_overwrite_updates_value(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "remember", "namespace": "n", "key": "a", "value": 1}, ctx)
    execute({"op": "remember", "namespace": "n", "key": "a", "value": 2,
             "importance": 0.1}, ctx)
    r = execute({"op": "recall", "namespace": "n", "key": "a"}, ctx)
    assert r["value"] == 2 and r["importance"] == 0.1
