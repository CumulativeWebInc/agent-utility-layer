"""Tests for agent_monitor."""
import importlib.util
import os
import sys
import pytest
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_agent_monitor", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_heartbeat_status(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "heartbeat", "agent": "a1", "status": "alive",
             "metrics": {"cpu": 0.5}}, ctx)
    s = execute({"op": "status", "agent": "a1"}, ctx)
    assert s["found"] is True and s["agent_status"] == "alive"
    assert s["stale"] is False and s["metrics"] == {"cpu": 0.5}


def test_stale_detection(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "heartbeat", "agent": "a1"}, ctx)
    time.sleep(0.05)
    s = execute({"op": "status", "agent": "a1", "stale_after_s": 0.01}, ctx)
    assert s["stale"] is True


def test_list_marks_stale(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "heartbeat", "agent": "a1"}, ctx)
    execute({"op": "heartbeat", "agent": "a2"}, ctx)
    time.sleep(0.05)
    lst = execute({"op": "list", "stale_after_s": 0.01}, ctx)
    assert {a["agent"] for a in lst["agents"]} == {"a1", "a2"}
    assert all(a["stale"] for a in lst["agents"])


def test_unknown_agent(tmp_path):
    ctx = FakeCtx(tmp_path)
    assert execute({"op": "status", "agent": "ghost"}, ctx)["found"] is False


def test_deregister(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "heartbeat", "agent": "a1"}, ctx)
    d = execute({"op": "deregister", "agent": "a1"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "status", "agent": "a1"}, ctx)["found"] is False


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "heartbeat"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "heartbeat", "agent": "a1", "metrics": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "status", "agent": "a1", "stale_after_s": -1}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
