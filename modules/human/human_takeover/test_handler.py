import os
import sys

import pytest

import importlib.util as _ilu

_handler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_spec = _ilu.spec_from_file_location("handler_under_test", _handler_path)
handler = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(handler)
from common import FakeCtx, ModuleError, ApprovalDenied

INPUTS = {"task_id": "task-42", "reason": "needs legal judgment", "handoff_note": "see thread"}


def test_happy_path_transfers_control():
    ctx = FakeCtx()
    result = handler.execute(dict(INPUTS), ctx)
    assert result["status"] == "control_transferred"
    assert result["takeover_id"].startswith("takeover_")
    assert result["control"] == "human"
    assert ctx.memory_get("task_control:task-42") == "human"
    stored = ctx.memory_get("human_takeover:%s" % result["takeover_id"])
    assert stored["status"] == "awaiting_human"
    assert ctx.bills[0][0] == 0.01


def test_missing_reason_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"task_id": "task-42"}, ctx)


def test_empty_task_id_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"task_id": "  ", "reason": "r"}, ctx)


def test_wrong_type_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"task_id": 42, "reason": "r"}, ctx)


def test_approval_denied_blocks_takeover():
    ctx = FakeCtx(approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert "task_control:task-42" not in ctx.memory


def test_output_schema_keys():
    ctx = FakeCtx()
    result = handler.execute(dict(INPUTS), ctx)
    assert set(result.keys()) == {"status", "takeover_id", "control"}


def test_approval_is_requested_before_transfer():
    ctx = FakeCtx()
    handler.execute(dict(INPUTS), ctx)
    assert ctx.approvals and "task-42" in ctx.approvals[0]
