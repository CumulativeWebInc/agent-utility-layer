"""send_voice — Crew C / communication pillar.

Place an outbound voice call via Twilio's REST API with inline TwiML
(text-to-speech of the supplied text). stdlib urllib only. External action:
requires ctx.approval_request(...) before dispatch. No credential -> AuthMissing.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import base64
import json as _json
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape as _xml_escape

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {"type": "string", "format": "phone"},
        "text": {"type": "string", "minLength": 1},
        "voice": {"type": "string"},
        "from_number": {"type": "string", "format": "phone"},
    },
    "required": ["to", "text"],
}

OUTPUT_KEYS = ["status", "call_sid"]

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
    voice = inputs.get("voice") or "alice"
    twiml = "<Response><Say voice=\"%s\">%s</Say></Response>" % (
        _xml_escape(voice), _xml_escape(inputs["text"]))
    url = "https://api.twilio.com/2010-04-01/Accounts/%s/Calls.json" % cred["account_sid"]
    data = urllib.parse.urlencode({
        "To": inputs["to"], "From": from_number, "Twiml": twiml,
    }).encode("utf-8")
    basic = base64.b64encode(("%s:%s" % (cred["account_sid"], cred["auth_token"])).encode()).decode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Authorization": "Basic " + basic})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise ModuleError("twilio voice request failed: %s: %s" % (type(exc).__name__, exc))
    if not body.get("sid"):
        raise ModuleError("twilio voice call failed: %s" % body)
    return {"status": body.get("status", "queued"), "call_sid": body["sid"]}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Place voice call to %s speaking %d chars" % (inputs["to"], len(inputs["text"])))
    cred = json_cred(ctx, "twilio", TWILIO_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_voice", {"to": inputs["to"], "approval_id": approval_id,
                           "call_sid": result["call_sid"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_voice execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
