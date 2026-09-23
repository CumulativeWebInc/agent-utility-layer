"""human_takeover — Crew C / human pillar.

Transfer control of a task from the agent to a human operator. This is a
control-plane change (the agent stops acting on the task), so it is treated
as destructive-adjacent: ctx.approval_request(...) is REQUIRED before the
transfer is recorded. The handoff record is stored via ctx.memory_set.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from datetime import datetime, timezone

from common import (  # noqa: E402
    ModuleError, ApprovalDenied,
    validate_inputs, new_id,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
        "handoff_note": {"type": "string"},
    },
    "required": ["task_id", "reason"],
}

OUTPUT_KEYS = ["status", "takeover_id", "control"]

PRICE_PER_EXEC_USD = 0.01


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Transfer control of task %r to a human. Reason: %s" % (
            inputs["task_id"], inputs["reason"][:160]))
    takeover_id = new_id("takeover")
    record = {
        "takeover_id": takeover_id,
        "task_id": inputs["task_id"],
        "reason": inputs["reason"],
        "handoff_note": inputs.get("handoff_note"),
        "control": "human",
        "status": "awaiting_human",
        "transferred_at": datetime.now(timezone.utc).isoformat(),
        "approval_id": approval_id,
    }
    ctx.memory_set("human_takeover:%s" % takeover_id, record)
    ctx.memory_set("task_control:%s" % inputs["task_id"], "human")
    ctx.log("human_takeover", {"takeover_id": takeover_id,
                               "task_id": inputs["task_id"],
                               "approval_id": approval_id})
    ctx.bill(PRICE_PER_EXEC_USD, "human_takeover execution")
    result = {"status": "control_transferred", "takeover_id": takeover_id,
              "control": "human"}
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
