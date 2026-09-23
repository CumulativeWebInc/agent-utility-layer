"""send_sms — Crew C / communication pillar.

Send an SMS via Twilio's REST API (stdlib urllib). External send: requires
ctx.approval_request(...) before dispatch. No credential -> AuthMissing.
Never fabricates a "sent" confirmation.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import base64
import json as _json
import urllib.parse
import urllib.request

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred, new_id,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {"type": "string", "format": "phone"},
        "message": {"type": "string", "minLength": 1},
        "from_number": {"type": "string", "format": "phone"},
    },
    "required": ["to", "message"],
}

OUTPUT_KEYS = ["status", "message_sid"]

TWILIO_SETUP_HINT = (
    "Store provider 'twilio' credentials (via apikey_vault) as JSON: "
    '{"account_sid": "AC...", "auth_token": "...", "from_number": "+15551234567"}.'
)

PRICE_PER_EXEC_USD = 0.001


def _provider_send(cred, inputs):
    for field in ("account_sid", "auth_token"):
        if not cred.get(field):
            raise ModuleError("twilio credential is missing required field '%s'" % field)
    from_number = inputs.get("from_number") or cred.get("from_number")
    if not from_number:
        raise ModuleError("no from_number: pass input 'from_number' or set it in the twilio credential")
    url = "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % cred["account_sid"]
    data = urllib.parse.urlencode({
        "To": inputs["to"], "From": from_number, "Body": inputs["message"],
    }).encode("utf-8")
    basic = base64.b64encode(("%s:%s" % (cred["account_sid"], cred["auth_token"])).encode()).decode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Authorization": "Basic " + basic})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise ModuleError("twilio sms request failed: %s: %s" % (type(exc).__name__, exc))
    if not body.get("sid"):
        raise ModuleError("twilio sms failed: %s" % body)
    return {"status": body.get("status", "queued"), "message_sid": body["sid"]}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Send SMS to %s (%d chars)" % (inputs["to"], len(inputs["message"])))
    cred = json_cred(ctx, "twilio", TWILIO_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_sms", {"to": inputs["to"], "approval_id": approval_id,
                         "message_sid": result["message_sid"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_sms execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
