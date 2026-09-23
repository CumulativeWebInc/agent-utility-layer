"""Tests for user_profile."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_user_profile", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_update_get_roundtrip(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "update", "user_id": "u1",
             "patch": {"name": "Black", "prefs": {"theme": "dark"}}}, ctx)
    r = execute({"op": "get", "user_id": "u1"}, ctx)
    assert r["found"] is True
    assert r["profile"] == {"name": "Black", "prefs": {"theme": "dark"}}


def test_deep_merge(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "update", "user_id": "u1",
             "patch": {"prefs": {"theme": "dark", "lang": "en"}}}, ctx)
    execute({"op": "update", "user_id": "u1",
             "patch": {"prefs": {"theme": "light"}}}, ctx)
    r = execute({"op": "get", "user_id": "u1"}, ctx)
    assert r["profile"]["prefs"] == {"theme": "light", "lang": "en"}


def test_get_field(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "update", "user_id": "u1",
             "patch": {"prefs": {"theme": "dark"}}}, ctx)
    f = execute({"op": "get_field", "user_id": "u1", "field": "prefs.theme"}, ctx)
    assert f["found"] is True and f["value"] == "dark"
    f2 = execute({"op": "get_field", "user_id": "u1", "field": "prefs.nope"}, ctx)
    assert f2["found"] is False


def test_get_missing_user(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "get", "user_id": "ghost"}, ctx)
    assert r["found"] is False and r["profile"] == {}


def test_delete(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "update", "user_id": "u1", "patch": {"a": 1}}, ctx)
    d = execute({"op": "delete", "user_id": "u1"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "get", "user_id": "u1"}, ctx)["found"] is False


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "update", "user_id": "u1", "patch": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "get"}, ctx)  # missing user_id
    with pytest.raises(ModuleError):
        execute({"op": "get_field", "user_id": "u1"}, ctx)  # missing field
    with pytest.raises(ModuleError):
        execute({"op": "nope", "user_id": "u1"}, ctx)
