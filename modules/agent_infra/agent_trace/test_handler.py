"""Tests for agent_trace."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_agent_trace", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_start_end_get_trace(tmp_path):
    ctx = FakeCtx(tmp_path)
    s = execute({"op": "start", "name": "root", "agent": "a1"}, ctx)
    c = execute({"op": "start", "name": "child", "agent": "a1",
                 "trace_id": s["trace_id"], "parent_id": s["span_id"]}, ctx)
    execute({"op": "end", "span_id": c["span_id"], "end_status": "ok",
             "output": {"n": 1}}, ctx)
    execute({"op": "end", "span_id": s["span_id"]}, ctx)
    t = execute({"op": "get_trace", "trace_id": s["trace_id"]}, ctx)
    assert t["found"] is True and t["span_count"] == 2
    root = t["tree"][0]
    assert root["name"] == "root" and len(root["children"]) == 1
    child = root["children"][0]
    assert child["name"] == "child" and child["output"] == {"n": 1}
    assert child["end_status"] == "ok"


def test_get_trace_missing(tmp_path):
    ctx = FakeCtx(tmp_path)
    assert execute({"op": "get_trace", "trace_id": "nope"}, ctx)["found"] is False


def test_list_traces(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "start", "name": "x", "agent": "a1"}, ctx)
    execute({"op": "start", "name": "y", "agent": "a2"}, ctx)
    all_t = execute({"op": "list_traces"}, ctx)
    assert len(all_t["traces"]) == 2
    a1 = execute({"op": "list_traces", "agent": "a1"}, ctx)
    assert len(a1["traces"]) == 1


def test_end_unknown_and_double_end(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "end", "span_id": "nope"}, ctx)
    s = execute({"op": "start", "name": "x", "agent": "a1"}, ctx)
    execute({"op": "end", "span_id": s["span_id"]}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "end", "span_id": s["span_id"]}, ctx)


def test_bad_parent_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "start", "name": "x", "agent": "a1",
                 "parent_id": "ghost-parent"}, ctx)


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "start", "agent": "a1"}, ctx)  # missing name
    with pytest.raises(ModuleError):
        execute({"op": "start", "name": "x"}, ctx)  # missing agent
    with pytest.raises(ModuleError):
        execute({"op": "list_traces", "limit": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
