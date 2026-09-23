"""send_slack — Crew C / communication pillar.

Post a message to Slack via an incoming webhook URL or a bot token
(chat.postMessage), stdlib urllib only. External send: requires
ctx.approval_request(...) before dispatch. No credential -> AuthMissing.
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
        "channel": {"type": "string"},
        "text": {"type": "string", "minLength": 1},
        "username": {"type": "string"},
    },
    "required": ["text"],
}

OUTPUT_KEYS = ["status", "ts"]

SLACK_SETUP_HINT = (
    "Store provider 'slack' credentials (via apikey_vault) as JSON with EITHER "
    '{"webhook_url": "https://hooks.slack.com/services/..."} (incoming webhook) '
    'OR {"bot_token": "xoxb-..."} (bot token; then input "channel" is required).'
)

PRICE_PER_EXEC_USD = 0.001


def _post(url, payload, headers=None):
    data = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise ModuleError("slack request failed: %s: %s" % (type(exc).__name__, exc))
    return raw


def _provider_send(cred, inputs):
    payload = {"text": inputs["text"]}
    if inputs.get("username"):
        payload["username"] = inputs["username"]
    if cred.get("webhook_url"):
        _post(cred["webhook_url"], payload)
        return {"status": "sent", "ts": "webhook"}
    if cred.get("bot_token"):
        channel = inputs.get("channel")
        if not channel:
            raise ModuleError("input 'channel' is required when using a bot_token credential")
        payload["channel"] = channel
        raw = _post("https://slack.com/api/chat.postMessage", payload,
                    {"Authorization": "Bearer " + cred["bot_token"]})
        try:
            body = _json.loads(raw)
        except Exception:
            raise ModuleError("slack returned non-JSON response: %r" % raw[:200])
        if not body.get("ok"):
            raise ModuleError("slack chat.postMessage failed: %s" % body)
        return {"status": "sent", "ts": body.get("ts", "")}
    raise ModuleError("slack credential must contain 'webhook_url' or 'bot_token'. " + SLACK_SETUP_HINT)


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Post Slack message (%d chars)%s" % (
            len(inputs["text"]),
            (" to " + inputs["channel"]) if inputs.get("channel") else ""))
    cred = json_cred(ctx, "slack", SLACK_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_slack", {"channel": inputs.get("channel"), "approval_id": approval_id,
                           "ts": result["ts"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_slack execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
