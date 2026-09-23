"""human_notify — Crew C / human pillar.

Push a notification to a human through the configured notification webhook
(channel: push/email/sms/in-app). Reaching a human is an external action:
requires ctx.approval_request(...) before dispatch. No credential -> AuthMissing.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json as _json
import urllib.request

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred, new_id,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "recipient": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "message": {"type": "string", "minLength": 1},
        "channel": {"type": "string", "enum": ["push", "email", "sms", "in-app"]},
    },
    "required": ["recipient", "title", "message"],
}

OUTPUT_KEYS = ["status", "notification_id"]

NOTIFY_SETUP_HINT = (
    "Store provider 'notify' credentials (via apikey_vault) as JSON: "
    '{"webhook_url": "https://your-endpoint/notify"} — the handler POSTs '
    '{"recipient", "title", "message", "channel"} as JSON.'
)

# Human-approval push modules price the human-loop at $0.01/execution
# (venture model default) instead of the $0.001 machine default.
PRICE_PER_EXEC_USD = 0.01


def _provider_send(cred, inputs):
    webhook_url = cred.get("webhook_url")
    if not webhook_url:
        raise ModuleError("notify credential is missing required field 'webhook_url'")
    payload = {
        "recipient": inputs["recipient"],
        "title": inputs["title"],
        "message": inputs["message"],
        "channel": inputs.get("channel") or "push",
    }
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise ModuleError("notify webhook failed: %s: %s" % (type(exc).__name__, exc))
    notification_id = new_id("notif")
    try:
        body = _json.loads(raw)
        notification_id = str(body.get("id") or body.get("notification_id") or notification_id)
    except Exception:
        pass
    return {"status": "sent", "notification_id": notification_id}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Notify human %r: %r" % (inputs["recipient"], inputs["title"]))
    cred = json_cred(ctx, "notify", NOTIFY_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("human_notify", {"recipient": inputs["recipient"], "approval_id": approval_id,
                             "notification_id": result["notification_id"]})
    ctx.bill(PRICE_PER_EXEC_USD, "human_notify execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
