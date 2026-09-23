"""human_signature — Crew C / human pillar.

Send a signature REQUEST to a human signer via the configured SMTP provider.
Honest scope: this sends an email asking the human to sign and records the
request — it is NOT a legal e-signature provider (no DocuSign/Adobe Sign
integration, no audit-trail certificate). Contacting a human is external:
requires ctx.approval_request(...) before dispatch. No credential -> AuthMissing.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from email.message import EmailMessage
from email.utils import make_msgid

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred, smtp_send, new_id,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "document_name": {"type": "string", "minLength": 1},
        "document_text": {"type": "string"},
        "signer_name": {"type": "string", "minLength": 1},
        "signer_email": {"type": "string", "format": "email"},
        "message": {"type": "string"},
    },
    "required": ["document_name", "signer_name", "signer_email"],
}

OUTPUT_KEYS = ["status", "request_id", "sent_to"]

SMTP_SETUP_HINT = (
    "Store provider 'smtp' credentials (via apikey_vault) as JSON: "
    '{"host": "smtp.example.com", "port": 587, "username": "user", '
    '"password": "APP_PASSWORD", "from_addr": "bot@example.com", "use_tls": true}.'
)

PRICE_PER_EXEC_USD = 0.01


def _provider_send(cred, inputs):
    request_id = new_id("sigreq")
    body_lines = [
        "Hello %s," % inputs["signer_name"],
        "",
        "You are requested to sign the document: %s" % inputs["document_name"],
        "Request ID: %s" % request_id,
    ]
    if inputs.get("message"):
        body_lines += ["", inputs["message"]]
    if inputs.get("document_text"):
        body_lines += ["", "--- Document text ---", "", inputs["document_text"]]
    body_lines += ["", "Reply to this email to confirm your signature."]
    msg = EmailMessage()
    msg["Subject"] = "Signature requested: %s" % inputs["document_name"]
    msg["From"] = cred["from_addr"]
    msg["To"] = inputs["signer_email"]
    msg["Message-ID"] = make_msgid(domain=cred["host"].split(":")[0])
    msg.set_content("\n".join(body_lines))
    smtp_send(cred, msg)
    return {"status": "sent", "request_id": request_id, "sent_to": inputs["signer_email"]}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Send signature request for %r to %s <%s>" % (
            inputs["document_name"], inputs["signer_name"], inputs["signer_email"]))
    cred = json_cred(ctx, "smtp", SMTP_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.memory_set("human_signature:%s" % result["request_id"],
                   {"document_name": inputs["document_name"],
                    "signer_email": inputs["signer_email"],
                    "status": "requested"})
    ctx.log("human_signature", {"request_id": result["request_id"],
                                "approval_id": approval_id})
    ctx.bill(PRICE_PER_EXEC_USD, "human_signature execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
