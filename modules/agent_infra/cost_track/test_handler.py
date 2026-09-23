"""Tests for cost_track."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_cost_track", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_record_and_totals(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "record", "agent": "a1", "capability": "send_email",
             "amount_usd": 0.001, "memo": "one send"}, ctx)
    execute({"op": "record", "agent": "a1", "capability": "send_email",
             "amount_usd": 0.002}, ctx)
    t = execute({"op": "totals", "agent": "a1"}, ctx)
    assert t["total_usd"] == pytest.approx(0.003) and t["count"] == 2


def test_totals_all_agents(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "record", "agent": "a1", "capability": "c1",
             "amount_usd": 1.0}, ctx)
    execute({"op": "record", "agent": "a2", "capability": "c1",
             "amount_usd": 2.0}, ctx)
    t = execute({"op": "totals"}, ctx)
    assert t["total_usd"] == pytest.approx(3.0) and t["count"] == 2


def test_by_capability(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "record", "agent": "a1", "capability": "c1",
             "amount_usd": 1.0}, ctx)
    execute({"op": "record", "agent": "a1", "capability": "c2",
             "amount_usd": 2.0}, ctx)
    b = execute({"op": "by_capability", "agent": "a1"}, ctx)
    assert b["rows"][0]["capability"] == "c2"
    assert b["rows"][0]["total_usd"] == pytest.approx(2.0)


def test_by_agent(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "record", "agent": "a1", "capability": "c1",
             "amount_usd": 5.0}, ctx)
    b = execute({"op": "by_agent"}, ctx)
    assert b["rows"] == [{"agent": "a1", "total_usd": 5.0, "count": 1}]


def test_negative_amount_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "record", "agent": "a1", "capability": "c1",
                 "amount_usd": -0.5}, ctx)


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "record", "agent": "a1", "capability": "c1"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "record", "agent": "a1", "capability": "c1",
                 "amount_usd": 1.0, "memo": 123}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "totals", "since_ts": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
