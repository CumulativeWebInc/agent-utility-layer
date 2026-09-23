"""send_email — Crew C / communication pillar.

Send an email via the configured SMTP provider (stdlib smtplib).
External send: requires ctx.approval_request(...) before dispatch.
No credential -> AuthMissing with setup instructions. Never fabricates "sent".
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from email.message import EmailMessage
from email.utils import make_msgid

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred, smtp_send,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {"type": "string", "format": "email"},
        "subject": {"type": "string", "minLength": 1},
        "body": {"type": "string", "minLength": 1},
        "cc": {"type": "array"},
        "bcc": {"type": "array"},
        "html_body": {"type": "string"},
        "reply_to": {"type": "string", "format": "email"},
    },
    "required": ["to", "subject", "body"],
}

OUTPUT_KEYS = ["status", "message_id"]

SMTP_SETUP_HINT = (
    "Store provider 'smtp' credentials (via apikey_vault) as JSON: "
    '{"host": "smtp.example.com", "port": 587, "username": "user", '
    '"password": "APP_PASSWORD", "from_addr": "bot@example.com", "use_tls": true}.'
)

PRICE_PER_EXEC_USD = 0.001


def _provider_send(cred, inputs):
    msg = EmailMessage()
    msg["Subject"] = inputs["subject"]
    msg["From"] = cred["from_addr"]
    msg["To"] = inputs["to"]
    for field, header in (("cc", "Cc"), ("bcc", "Bcc")):
        addrs = inputs.get(field) or []
        if addrs:
            for addr in addrs:
                if "@" not in addr:
                    raise ModuleError("invalid email in '%s': %r" % (field, addr))
            msg[header] = ", ".join(addrs)
    # smtplib.send_message envelopes To/Cc/Bcc and strips the Bcc header.
    msg["Message-ID"] = make_msgid(domain=cred["host"].split(":")[0])
    if inputs.get("reply_to"):
        msg["Reply-To"] = inputs["reply_to"]
    msg.set_content(inputs["body"])
    if inputs.get("html_body"):
        msg.add_alternative(inputs["html_body"], subtype="html")
    smtp_send(cred, msg)
    return {"status": "sent", "message_id": msg["Message-ID"]}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Send email to %s — subject: %r" % (inputs["to"], inputs["subject"]))
    cred = json_cred(ctx, "smtp", SMTP_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_email", {"to": inputs["to"], "approval_id": approval_id,
                           "message_id": result["message_id"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_email execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
