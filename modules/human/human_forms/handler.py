"""human_forms — Crew C / human pillar.

Build a structured form definition (title + typed fields) that a human can
fill in. Creation only — it does not send anything to anyone, so no approval
is required here; delivering the form to a human goes through human_notify.
The form spec is stored via ctx.memory_set and a demo preview path is returned.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from common import (  # noqa: E402
    ModuleError, validate_inputs, new_id,
)

FIELD_TYPES = ["text", "number", "boolean", "choice", "date"]

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "fields": {"type": "array"},
        "submit_label": {"type": "string"},
    },
    "required": ["title", "fields"],
}

OUTPUT_KEYS = ["status", "form_id", "field_count", "preview_path"]

PRICE_PER_EXEC_USD = 0.001


def _validate_fields(fields):
    if not fields:
        raise ModuleError("input 'fields' must be a non-empty array")
    seen = set()
    for i, field in enumerate(fields):
        if not isinstance(field, dict):
            raise ModuleError("fields[%d] must be an object" % i)
        name = field.get("name")
        ftype = field.get("type")
        if not name or not isinstance(name, str):
            raise ModuleError("fields[%d] is missing required 'name'" % i)
        if name in seen:
            raise ModuleError("duplicate field name: %r" % name)
        seen.add(name)
        if ftype not in FIELD_TYPES:
            raise ModuleError("fields[%d].type must be one of %s, got %r" % (i, FIELD_TYPES, ftype))
        if ftype == "choice":
            options = field.get("options")
            if not options or not isinstance(options, list):
                raise ModuleError("fields[%d] of type 'choice' requires an 'options' array" % i)
        if "required" in field and not isinstance(field["required"], bool):
            raise ModuleError("fields[%d].required must be boolean" % i)


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    _validate_fields(inputs["fields"])
    form_id = new_id("form")
    spec = {
        "form_id": form_id,
        "title": inputs["title"],
        "fields": inputs["fields"],
        "submit_label": inputs.get("submit_label") or "Submit",
        "status": "draft",
    }
    ctx.memory_set("human_forms:%s" % form_id, spec)
    ctx.log("human_forms", {"form_id": form_id, "field_count": len(inputs["fields"])})
    ctx.bill(PRICE_PER_EXEC_USD, "human_forms execution")
    result = {
        "status": "created",
        "form_id": form_id,
        "field_count": len(inputs["fields"]),
        "preview_path": "/demo/human_forms/%s" % form_id,
    }
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
