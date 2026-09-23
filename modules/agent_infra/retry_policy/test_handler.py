"""Tests for retry_policy."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_retry_policy", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)

    # retry_policy never touches the store for plan/next_delay


def test_plan_exponential(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "plan", "policy": {"max_attempts": 4, "base_delay_s": 1.0,
                                          "backoff": "exponential", "factor": 2.0,
                                          "jitter_s": 0.0}, "seed": 7}, ctx)
    assert r["delays"] == [1.0, 2.0, 4.0]


def test_plan_linear_and_constant(tmp_path):
    ctx = FakeCtx(tmp_path)
    lin = execute({"op": "plan", "policy": {"max_attempts": 3, "base_delay_s": 2.0,
                                            "backoff": "linear", "jitter_s": 0.0},
                   "seed": 1}, ctx)
    assert lin["delays"] == [2.0, 4.0]
    const = execute({"op": "plan", "policy": {"max_attempts": 3, "base_delay_s": 5.0,
                                              "backoff": "constant", "jitter_s": 0.0},
                     "seed": 1}, ctx)
    assert const["delays"] == [5.0, 5.0]


def test_max_delay_cap(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "plan", "policy": {"max_attempts": 4, "base_delay_s": 10.0,
                                          "backoff": "exponential", "factor": 10.0,
                                          "max_delay_s": 25.0, "jitter_s": 0.0},
                   "seed": 1}, ctx)
    assert r["delays"] == [10.0, 25.0, 25.0]


def test_next_delay_exhausted(tmp_path):
    ctx = FakeCtx(tmp_path)
    p = {"max_attempts": 2, "base_delay_s": 1.0}
    d1 = execute({"op": "next_delay", "policy": p, "attempt": 1, "seed": 3}, ctx)
    assert d1["exhausted"] is False and d1["delay_seconds"] == 1.0
    d2 = execute({"op": "next_delay", "policy": p, "attempt": 2, "seed": 3}, ctx)
    assert d2["exhausted"] is True and d2["delay_seconds"] == 0.0


def test_record_failure_dead_letters(tmp_path):
    ctx = FakeCtx(tmp_path)
    p = {"max_attempts": 2}
    r1 = execute({"op": "record_failure", "operation_id": "op1", "error": "boom",
                  "policy": p}, ctx)
    assert r1["attempts"] == 1 and r1["dead_lettered"] is False
    r2 = execute({"op": "record_failure", "operation_id": "op1", "error": "boom2",
                  "policy": p}, ctx)
    assert r2["attempts"] == 2 and r2["dead_lettered"] is True
    dl = execute({"op": "dead_letter"}, ctx)
    assert len(dl["entries"]) == 1
    assert dl["entries"][0]["operation_id"] == "op1"


def test_requeue(tmp_path):
    ctx = FakeCtx(tmp_path)
    p = {"max_attempts": 1}
    execute({"op": "record_failure", "operation_id": "op1", "error": "x",
             "policy": p}, ctx)
    r = execute({"op": "requeue", "operation_id": "op1"}, ctx)
    assert r["requeued"] is True
    assert execute({"op": "dead_letter"}, ctx)["entries"] == []


def test_invalid_policy(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "plan", "policy": {"max_attempts": 0}}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "plan", "policy": {"backoff": "weird"}}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "plan", "policy": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "next_delay", "policy": {}, "attempt": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "record_failure", "policy": {}}, ctx)  # missing operation_id
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
