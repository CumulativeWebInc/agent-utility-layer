"""Reference module proving CONTRACT.md end to end.

SIMULATED provider only — every result is labeled simulated. Real mode still
requires a credential (proving AuthMissing) and destructive=true exercises
ctx.approval_request (proving ApprovalDenied). Nothing here touches a real
provider; nothing is fabricated as real.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "spine"))

from registry import validate_inputs  # noqa: E402


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


CAPABILITY_PATH = os.path.join(os.path.dirname(__file__), "capability.json")


def _schema():
    import json
    with open(CAPABILITY_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)["inputs_schema"]


def execute(inputs: dict, ctx) -> dict:
    """Echo a message. See module docstring for the simulated-provider rules."""
    errors = validate_inputs(_schema(), inputs)
    if errors:
        raise ModuleError("invalid inputs: " + "; ".join(errors))

    message = inputs["message"]
    if ctx.demo:
        # Demo: simulated provider, no credential needed, clearly labeled.
        echo = message.upper() if inputs.get("uppercase") else message
        ctx.log("template_demo.demo_echo", {"length": len(message)})
        return {"status": "ok", "echo": echo, "demo": True, "simulated": True}

    # Real mode: credential is mandatory — missing -> AuthMissing with setup help.
    credential = ctx.auth_get("template_provider")
    if not credential:
        raise AuthMissing("empty credential for provider 'template_provider'")

    if inputs.get("destructive"):
        approval_id = ctx.approval_request(
            f"template_demo destructive echo of {len(message)} chars",
            timeout_seconds=300,
        )
        ctx.log("template_demo.approved", {"approval_id": approval_id})

    echo = message.upper() if inputs.get("uppercase") else message
    ctx.log("template_demo.echo", {"length": len(message)})
    return {"status": "ok", "echo": echo, "demo": False, "simulated": True}
