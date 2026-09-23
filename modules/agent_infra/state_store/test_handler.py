"""Tests for state_store."""
import importlib.util
import os
import sys
import pytest
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_state_store", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_set_get_roundtrip(tmp_path):
    ctx = FakeCtx(tmp_path)
    s = execute({"op": "set", "namespace": "ns", "key": "k", "value": {"a": 1}}, ctx)
    assert s["version"] == 1
    g = execute({"op": "get", "namespace": "ns", "key": "k"}, ctx)
    assert g["found"] is True and g["value"] == {"a": 1} and g["version"] == 1


def test_set_bumps_version(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "namespace": "ns", "key": "k", "value": 1}, ctx)
    s = execute({"op": "set", "namespace": "ns", "key": "k", "value": 2}, ctx)
    assert s["version"] == 2


def test_get_missing(tmp_path):
    ctx = FakeCtx(tmp_path)
    g = execute({"op": "get", "namespace": "ns", "key": "nope"}, ctx)
    assert g["found"] is False


def test_ttl_expiry(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "namespace": "ns", "key": "k", "value": 1,
             "ttl_seconds": 0.05}, ctx)
    time.sleep(0.08)
    assert execute({"op": "get", "namespace": "ns", "key": "k"}, ctx)["found"] is False


def test_cas_success_and_conflict(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "namespace": "ns", "key": "k", "value": 1}, ctx)
    ok = execute({"op": "cas", "namespace": "ns", "key": "k",
                  "expected_version": 1, "value": 2}, ctx)
    assert ok["version"] == 2
    with pytest.raises(ModuleError):
        execute({"op": "cas", "namespace": "ns", "key": "k",
                 "expected_version": 1, "value": 3}, ctx)
    g = execute({"op": "get", "namespace": "ns", "key": "k"}, ctx)
    assert g["value"] == 2  # failed CAS did not write


def test_cas_missing_key(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "cas", "namespace": "ns", "key": "nope",
                 "expected_version": 1, "value": 1}, ctx)


def test_list_prefix_and_delete(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "set", "namespace": "ns", "key": "a.1", "value": 1}, ctx)
    execute({"op": "set", "namespace": "ns", "key": "a.2", "value": 2}, ctx)
    execute({"op": "set", "namespace": "ns", "key": "b.1", "value": 3}, ctx)
    l = execute({"op": "list", "namespace": "ns", "prefix": "a."}, ctx)
    assert [k["key"] for k in l["keys"]] == ["a.1", "a.2"]
    d = execute({"op": "delete", "namespace": "ns", "key": "a.1"}, ctx)
    assert d["deleted"] == 1


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "set", "namespace": "ns", "key": "k",
                 "value": 1, "ttl_seconds": -1}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "set", "namespace": "ns", "value": 1}, ctx)  # missing key
    with pytest.raises(ModuleError):
        execute({"op": "get", "key": "k"}, ctx)  # missing namespace
    with pytest.raises(ModuleError):
        execute({"op": "nope", "namespace": "ns"}, ctx)
