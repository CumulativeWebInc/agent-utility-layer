"""Tests for mem_short_term."""
import importlib.util
import os
import sys
import pytest
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_mem_short_term", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_set_get_roundtrip(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "set", "session_id": "s1", "key": "k", "value": {"a": 1}}, ctx)
    assert r["status"] == "ok"
    g = execute({"op": "get", "session_id": "s1", "key": "k"}, ctx)
    assert g["found"] is True and g["value"] == {"a": 1}


def test_get_missing_key(tmp_path):
    ctx = FakeCtx(tmp_path)
    g = execute({"op": "get", "session_id": "s1", "key": "nope"}, ctx)
    assert g["found"] is False and g["value"] is None


def test_ttl_expiry(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "session_id": "s1", "key": "k", "value": 1, "ttl_seconds": 0.05}, ctx)
    time.sleep(0.08)
    g = execute({"op": "get", "session_id": "s1", "key": "k"}, ctx)
    assert g["found"] is False


def test_list_and_clear(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "session_id": "s1", "key": "a", "value": 1}, ctx)
    execute({"op": "set", "session_id": "s1", "key": "b", "value": 2}, ctx)
    lst = execute({"op": "list", "session_id": "s1"}, ctx)
    assert {e["key"] for e in lst["entries"]} == {"a", "b"}
    c = execute({"op": "clear", "session_id": "s1"}, ctx)
    assert c["cleared"] == 2
    assert execute({"op": "list", "session_id": "s1"}, ctx)["entries"] == []


def test_delete(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "session_id": "s1", "key": "a", "value": 1}, ctx)
    d = execute({"op": "delete", "session_id": "s1", "key": "a"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "get", "session_id": "s1", "key": "a"}, ctx)["found"] is False


def test_invalid_op_and_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "bogus"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "set", "session_id": "s1"}, ctx)  # missing key/value
    with pytest.raises(ModuleError):
        execute({"op": "set", "session_id": "s1", "key": "k", "value": 1,
                 "ttl_seconds": -5}, ctx)
    with pytest.raises(ModuleError):
        execute("not-a-dict", ctx)
