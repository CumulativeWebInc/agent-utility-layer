"""Tests for agent_log."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_agent_log", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_write_query(tmp_path):
    ctx = FakeCtx(tmp_path)
    w = execute({"op": "write", "agent": "a1", "level": "INFO",
                 "event": "started", "data": {"x": 1}}, ctx)
    assert w["status"] == "ok" and w["entry_id"]
    q = execute({"op": "query", "agent": "a1"}, ctx)
    assert q["count"] == 1
    assert q["entries"][0]["event"] == "started"


def test_query_filters(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "write", "agent": "a1", "level": "INFO", "event": "e1"}, ctx)
    execute({"op": "write", "agent": "a1", "level": "ERROR", "event": "e2"}, ctx)
    execute({"op": "write", "agent": "a2", "level": "INFO", "event": "e1"}, ctx)
    assert execute({"op": "query", "level": "ERROR"}, ctx)["count"] == 1
    assert execute({"op": "query", "event": "e1"}, ctx)["count"] == 2
    assert execute({"op": "query", "agent": "a2", "event": "e1"}, ctx)["count"] == 1


def test_tail_and_limit(tmp_path):
    ctx = FakeCtx(tmp_path)
    for i in range(5):
        execute({"op": "write", "agent": "a1", "level": "INFO",
                 "event": f"e{i}"}, ctx)
    t = execute({"op": "tail", "limit": 2}, ctx)
    assert len(t["entries"]) == 2
    assert t["entries"][0]["event"] == "e4"  # newest first


def test_credential_like_data_refused(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "write", "agent": "a1", "level": "INFO", "event": "e",
                 "data": {"api_key": "sekret"}}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "write", "agent": "a1", "level": "INFO", "event": "e",
                 "data": {"password": "x"}}, ctx)


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "write", "agent": "a1", "level": "NOPE", "event": "e"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "write", "level": "INFO", "event": "e"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "query", "limit": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)


def test_empty_log_query(tmp_path):
    ctx = FakeCtx(tmp_path)
    q = execute({"op": "query", "agent": "nobody"}, ctx)
    assert q["count"] == 0 and q["entries"] == []
