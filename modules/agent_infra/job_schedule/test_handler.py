"""Tests for job_schedule."""
import importlib.util
import os
import sys
import pytest
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_job_schedule", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_create_interval_due(tmp_path):
    ctx = FakeCtx(tmp_path)
    c = execute({"op": "create", "name": "j1", "schedule": "every 60s",
                 "payload": {"x": 1}}, ctx)
    assert c["status"] == "ok" and c["next_run"] > time.time()
    due = execute({"op": "due"}, ctx)
    assert due["due"] == []  # not due yet
    due2 = execute({"op": "due", "now_ts": c["next_run"] + 1}, ctx)
    assert [j["name"] for j in due2["due"]] == ["j1"]


def test_mark_run_advances(tmp_path):
    ctx = FakeCtx(tmp_path)
    c = execute({"op": "create", "name": "j1", "schedule": "every 60s"}, ctx)
    m = execute({"op": "mark_run", "name": "j1", "now_ts": c["next_run"] + 1}, ctx)
    assert m["next_run"] > c["next_run"]
    assert execute({"op": "due", "now_ts": c["next_run"] + 1}, ctx)["due"] == []


def test_cron_next_run(tmp_path):
    ctx = FakeCtx(tmp_path)
    c = execute({"op": "create", "name": "daily", "schedule": "0 9 * * *"}, ctx)
    dt = time.gmtime(c["next_run"])
    assert (dt.tm_hour, dt.tm_min) == (9, 0)
    assert c["next_run"] > time.time()


def test_cron_step_and_list_syntax(tmp_path):
    ctx = FakeCtx(tmp_path)
    c = execute({"op": "create", "name": "q", "schedule": "*/15 * * * *"}, ctx)
    assert time.gmtime(c["next_run"]).tm_min % 15 == 0


def test_disabled_not_due(tmp_path):
    ctx = FakeCtx(tmp_path)
    c = execute({"op": "create", "name": "j1", "schedule": "every 1s",
                 "enabled": False}, ctx)
    due = execute({"op": "due", "now_ts": c["next_run"] + 5}, ctx)
    assert due["due"] == []


def test_list_delete_and_next_runs(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "create", "name": "j1", "schedule": "every 60s"}, ctx)
    lst = execute({"op": "list"}, ctx)
    assert [j["name"] for j in lst["jobs"]] == ["j1"]
    nr = execute({"op": "next_runs"}, ctx)
    assert nr["jobs"][0]["next_run"] > time.time()
    d = execute({"op": "delete", "name": "j1"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "list"}, ctx)["jobs"] == []


def test_invalid_schedule_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "create", "name": "j", "schedule": "someday"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "create", "name": "j", "schedule": "61 * * * *"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "create", "name": "j", "schedule": "every 0s"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "create", "name": "j", "schedule": "every 5x"}, ctx)


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "create", "schedule": "every 60s"}, ctx)  # missing name
    with pytest.raises(ModuleError):
        execute({"op": "mark_run", "name": "ghost"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "due", "now_ts": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
