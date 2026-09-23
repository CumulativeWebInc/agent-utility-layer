"""send_push — Crew C / communication pillar.

Deliver a push notification through a generic provider HTTP hook
(stdlib urllib). The credential maps to the provider of your choice
(FCM, OneSignal, ntfy, ...). External send: requires ctx.approval_request(...)
before dispatch. No credential -> AuthMissing.
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
        "target": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "body": {"type": "string", "minLength": 1},
        "data": {"type": "object"},
    },
    "required": ["target", "title", "body"],
}

OUTPUT_KEYS = ["status", "receipt"]

PUSH_SETUP_HINT = (
    "Store provider 'push' credentials (via apikey_vault) as JSON: "
    '{"endpoint_url": "https://your-push-provider/v1/send", "api_key": "...", '
    '"auth_scheme": "Bearer"} — the handler POSTs '
    '{"target", "title", "body", "data"?} as JSON with an Authorization header.'
)

PRICE_PER_EXEC_USD = 0.001


def _provider_send(cred, inputs):
    endpoint = cred.get("endpoint_url")
    api_key = cred.get("api_key")
    if not endpoint or not api_key:
        raise ModuleError("push credential must contain 'endpoint_url' and 'api_key'")
    scheme = cred.get("auth_scheme", "Bearer")
    payload = {"target": inputs["target"], "title": inputs["title"], "body": inputs["body"]}
    if inputs.get("data"):
        payload["data"] = inputs["data"]
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": "%s %s" % (scheme, api_key)})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise ModuleError("push provider request failed: %s: %s" % (type(exc).__name__, exc))
    receipt = raw[:200]
    try:
        body = _json.loads(raw)
        receipt = str(body.get("id") or body.get("receipt") or body.get("message_id") or raw[:200])
    except Exception:
        pass
    return {"status": "sent", "receipt": receipt}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Send push notification to %r: %r" % (inputs["target"], inputs["title"]))
    cred = json_cred(ctx, "push", PUSH_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_push", {"target": inputs["target"], "approval_id": approval_id,
                          "receipt": result["receipt"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_push execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
