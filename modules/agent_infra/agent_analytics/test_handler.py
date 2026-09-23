"""Tests for agent_analytics."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_agent_analytics", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

_log_spec = importlib.util.spec_from_file_location(
    "aul_handler_agent_log",
    os.path.normpath(os.path.join(_HERE, "..", "agent_log", "handler.py")))
log_handler = importlib.util.module_from_spec(_log_spec)
_log_spec.loader.exec_module(log_handler)

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def _write(ctx, agent, level, event):
    log_handler.execute({"op": "write", "agent": agent, "level": level,
                         "event": event}, ctx)


def test_summary_counts(tmp_path):
    ctx = FakeCtx(tmp_path)
    _write(ctx, "a1", "INFO", "started")
    _write(ctx, "a1", "INFO", "started")
    _write(ctx, "a1", "ERROR", "crashed")
    s = execute({"op": "summary", "agent": "a1"}, ctx)
    assert s["total"] == 3
    assert s["by_level"] == {"INFO": 2, "ERROR": 1}
    assert s["by_event"][0] == {"event": "started", "count": 2}
    assert s["error_rate"] == pytest.approx(1 / 3)


def test_summary_empty_is_zero(tmp_path):
    ctx = FakeCtx(tmp_path)
    s = execute({"op": "summary", "agent": "nobody"}, ctx)
    assert s["total"] == 0 and s["error_rate"] == 0.0


def test_errors_op(tmp_path):
    ctx = FakeCtx(tmp_path)
    _write(ctx, "a1", "INFO", "ok")
    _write(ctx, "a1", "ERROR", "boom")
    e = execute({"op": "errors", "agent": "a1"}, ctx)
    assert e["count"] == 1 and e["entries"][0]["event"] == "boom"


def test_event_counts(tmp_path):
    ctx = FakeCtx(tmp_path)
    _write(ctx, "a1", "INFO", "started")
    _write(ctx, "a2", "INFO", "started")
    _write(ctx, "a2", "INFO", "stopped")
    c = execute({"op": "event_counts"}, ctx)
    assert c["total"] == 3
    assert c["counts"] == {"started": 2, "stopped": 1}


def test_window_hours_filters(tmp_path):
    import json, time as _t
    ctx = FakeCtx(tmp_path)
    # deterministic: backdate one entry 2h, keep one fresh
    _write(ctx, "a1", "INFO", "fresh")
    path = os.path.join(str(tmp_path), "agent_log.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"entry_id": "old1", "ts": _t.time() - 7200,
                            "agent": "a1", "level": "INFO",
                            "event": "stale", "data": {}}) + "\n")
    s1 = execute({"op": "summary", "agent": "a1", "window_hours": 1}, ctx)
    assert s1["total"] == 1
    assert s1["by_event"][0]["event"] == "fresh"
    s3 = execute({"op": "summary", "agent": "a1", "window_hours": 3}, ctx)
    assert s3["total"] == 2


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "summary", "window_hours": -1}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "errors", "limit": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
