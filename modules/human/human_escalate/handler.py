"""human_escalate — Crew C / human pillar.

Escalate an issue to a human owner with a priority level. The escalation is
recorded internally (ctx.memory_set); looping a human in is an external action
so ctx.approval_request(...) is required before the record is created.
No provider credential is needed (no external API call is made by this module
itself — pair with human_notify to actually page the owner).
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
        "summary": {"type": "string", "minLength": 1},
        "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "owner": {"type": "string"},
        "context": {"type": "string"},
    },
    "required": ["summary", "priority"],
}

OUTPUT_KEYS = ["status", "escalation_id", "priority"]

PRICE_PER_EXEC_USD = 0.01


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Escalate [%s] to human%s: %s" % (
            inputs["priority"].upper(),
            (" (" + inputs["owner"] + ")") if inputs.get("owner") else "",
            inputs["summary"][:120]))
    escalation_id = new_id("esc")
    record = {
        "escalation_id": escalation_id,
        "summary": inputs["summary"],
        "priority": inputs["priority"],
        "owner": inputs.get("owner"),
        "context": inputs.get("context"),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approval_id": approval_id,
    }
    ctx.memory_set("human_escalate:%s" % escalation_id, record)
    ctx.log("human_escalate", {"escalation_id": escalation_id,
                               "priority": inputs["priority"],
                               "approval_id": approval_id})
    ctx.bill(PRICE_PER_EXEC_USD, "human_escalate execution")
    result = {"status": "escalated", "escalation_id": escalation_id,
              "priority": inputs["priority"]}
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
