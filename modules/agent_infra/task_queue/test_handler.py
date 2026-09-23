"""Tests for task_queue."""
import importlib.util
import os
import sys
import pytest
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_task_queue", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_enqueue_lease_complete(tmp_path):
    ctx = FakeCtx(tmp_path)
    e = execute({"op": "enqueue", "queue": "q", "payload": {"n": 1}}, ctx)
    l = execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)
    assert l["leased"] is True
    assert l["task"]["task_id"] == e["task_id"]
    assert l["task"]["status"] == "leased" and l["task"]["worker"] == "w1"
    c = execute({"op": "complete", "task_id": e["task_id"]}, ctx)
    assert c["status"] == "ok"
    assert execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)["leased"] is False


def test_fifo_and_priority(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "enqueue", "queue": "q", "payload": {"n": 1}, "priority": 0}, ctx)
    execute({"op": "enqueue", "queue": "q", "payload": {"n": 2}, "priority": 5}, ctx)
    l = execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)
    assert l["task"]["payload"] == {"n": 2}  # priority wins
    l2 = execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)
    assert l2["task"]["payload"] == {"n": 1}


def test_lease_expiry_revisible(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "enqueue", "queue": "q", "payload": {"n": 1}}, ctx)
    l = execute({"op": "lease", "queue": "q", "worker": "w1", "lease_seconds": 0.05}, ctx)
    assert l["leased"] is True
    time.sleep(0.08)
    l2 = execute({"op": "lease", "queue": "q", "worker": "w2"}, ctx)
    assert l2["leased"] is True and l2["task"]["worker"] == "w2"


def test_fail_requeue_then_dead(tmp_path):
    ctx = FakeCtx(tmp_path)
    e = execute({"op": "enqueue", "queue": "q", "payload": {"n": 1}}, ctx)
    execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)
    f = execute({"op": "fail", "task_id": e["task_id"], "error": "boom",
                 "max_attempts": 2}, ctx)
    assert f["new_status"] == "pending" and f["attempts"] == 1
    execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)
    f2 = execute({"op": "fail", "task_id": e["task_id"], "error": "boom",
                  "max_attempts": 2}, ctx)
    assert f2["new_status"] == "dead"
    assert execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)["leased"] is False


def test_stats_and_purge(tmp_path):
    ctx = FakeCtx(tmp_path)
    e1 = execute({"op": "enqueue", "queue": "q", "payload": {"n": 1}}, ctx)
    execute({"op": "enqueue", "queue": "q", "payload": {"n": 2}}, ctx)
    execute({"op": "lease", "queue": "q", "worker": "w1"}, ctx)
    execute({"op": "complete", "task_id": e1["task_id"]}, ctx)
    s = execute({"op": "stats", "queue": "q"}, ctx)
    assert s["stats"] == {"done": 1, "pending": 1}
    p = execute({"op": "purge_done", "queue": "q"}, ctx)
    assert p["purged"] == 1


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "enqueue", "queue": "q", "payload": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "lease", "queue": "q", "worker": "w", "lease_seconds": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "complete", "task_id": "ghost"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "fail", "task_id": "ghost"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
