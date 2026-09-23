import os
import sys

import pytest

import importlib.util as _ilu

_handler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_spec = _ilu.spec_from_file_location("handler_under_test", _handler_path)
handler = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(handler)
from common import FakeCtx, ModuleError, ApprovalDenied

INPUTS = {"summary": "DB failover stuck", "priority": "critical", "owner": "oncall"}


def test_happy_path_creates_escalation():
    ctx = FakeCtx()
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "escalated",
                      "escalation_id": result["escalation_id"],
                      "priority": "critical"}
    assert result["escalation_id"].startswith("esc_")
    stored = ctx.memory_get("human_escalate:%s" % result["escalation_id"])
    assert stored["status"] == "open"
    assert stored["owner"] == "oncall"
    assert ctx.bills[0][0] == 0.01


def test_missing_summary_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"priority": "high"}, ctx)


def test_bad_priority_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"summary": "x", "priority": "extreme"}, ctx)


def test_unknown_input_rejected():
    ctx = FakeCtx()
    bad = dict(INPUTS); bad["pager"] = True
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_approval_denied_blocks_escalation():
    ctx = FakeCtx(approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert ctx.memory == {}, "no record may be created after denied approval"


def test_output_schema_keys():
    ctx = FakeCtx()
    result = handler.execute(dict(INPUTS), ctx)
    assert set(result.keys()) == {"status", "escalation_id", "priority"}


def test_approval_is_requested_before_record():
    ctx = FakeCtx()
    handler.execute(dict(INPUTS), ctx)
    assert ctx.approvals, "escalation must request approval first"
