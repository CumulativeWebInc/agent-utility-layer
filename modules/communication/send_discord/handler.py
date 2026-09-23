"""send_discord — Crew C / communication pillar.

Post a message to a Discord channel via an incoming webhook URL
(stdlib urllib). External send: requires ctx.approval_request(...) before
dispatch. No credential -> AuthMissing.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json as _json
import urllib.request

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string", "minLength": 1},
        "username": {"type": "string"},
    },
    "required": ["message"],
}

OUTPUT_KEYS = ["status", "message_id"]

DISCORD_SETUP_HINT = (
    "Store provider 'discord' credentials (via apikey_vault) as JSON: "
    '{"webhook_url": "https://discord.com/api/webhooks/..."} '
    "(create in Discord: channel settings -> Integrations -> Webhooks)."
)

PRICE_PER_EXEC_USD = 0.001


def _provider_send(cred, inputs):
    webhook_url = cred.get("webhook_url")
    if not webhook_url:
        raise ModuleError("discord credential is missing required field 'webhook_url'")
    payload = {"content": inputs["message"], "wait": True}
    if inputs.get("username"):
        payload["username"] = inputs["username"]
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url + ("&wait=true" if "?" in webhook_url else "?wait=true"),
                                 data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise ModuleError("discord webhook request failed: %s: %s" % (type(exc).__name__, exc))
    return {"status": "sent", "message_id": str(body.get("id", ""))}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Post Discord message (%d chars)" % len(inputs["message"]))
    cred = json_cred(ctx, "discord", DISCORD_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_discord", {"approval_id": approval_id,
                             "message_id": result["message_id"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_discord execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
