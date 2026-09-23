"""approval_request — POST /v1/approval/request: 1-tap human gate.

Real logic, $0, stdlib only (hmac + secrets):
  - Validates inputs (channel, E.164-ish phone, summary, timeout).
  - Creates a signed pending approval record stored via ctx.memory under
    "aul:approval:{request_id}" and returns request_id, pending status,
    expires_at, and a 1-tap approval URL.
  - Signature: HMAC-SHA256 with the key from ctx.auth_get('approval_signing_key').
    If unconfigured, an ephemeral per-machine key is generated, stored in
    ctx.memory, and the record is HONESTLY labeled signature_mode
    "local_ephemeral" (verifiable by this machine only).
  - Notification delivery: this module CREATES the pending record and the
    approval URL — it never claims an SMS/WhatsApp/push was sent. Delivery
    status is always honest: "not_attempted" when the channel provider
    credential is missing, "queued_locally" otherwise, with a note that actual
    dispatch is done by the provider integration (Crew C's send_* modules),
    which will raise AuthMissing on unconfigured credentials.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

EXEC_PRICE_USD = 0.01  # human-approval push price per the venture model
CHANNELS = {"sms", "whatsapp", "push"}
PHONE_RE = re.compile(r"^\+\d{7,15}$")
SIGNING_KEY_STORE = "aul:approval_signing_key_v1"
RECORD_PREFIX = "aul:approval:"
APPROVAL_URL_BASE = "https://api.agent-utility-layer.io/v1/approval"
MIN_TIMEOUT_S = 30
MAX_TIMEOUT_S = 86_400


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _signing_key(ctx) -> tuple[str, str]:
    """Return (key, mode). mode is 'configured' or 'local_ephemeral'."""
    try:
        key = ctx.auth_get("approval_signing_key")
        if isinstance(key, str) and key:
            return key, "configured"
    except AuthMissing:
        pass
    key = ctx.memory_get(SIGNING_KEY_STORE)
    if not isinstance(key, str) or not key:
        key = secrets.token_hex(32)
        ctx.memory_set(SIGNING_KEY_STORE, key)
    return key, "local_ephemeral"


def _sign(record: dict, key: str) -> str:
    payload = "|".join(
        str(record[k]) for k in ("request_id", "user_id", "action_summary", "expires_at")
    )
    return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(record: dict, key: str) -> bool:
    """Verify a pending approval record has not been tampered with."""
    try:
        return hmac.compare_digest(record["signature"], _sign(record, key))
    except (KeyError, TypeError):
        return False


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. Returns a dict matching outputs_schema."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    user_id = inputs.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ModuleError("user_id is required and must be a non-empty string")

    channel = inputs.get("channel")
    if channel not in CHANNELS:
        raise ModuleError(
            "invalid channel %r; must be one of %s" % (channel, sorted(CHANNELS))
        )

    recipient_phone = inputs.get("recipient_phone")
    if not isinstance(recipient_phone, str) or not PHONE_RE.match(recipient_phone):
        raise ModuleError(
            "recipient_phone must be E.164 format, e.g. '+15550192834'"
        )

    action_summary = inputs.get("action_summary")
    if not isinstance(action_summary, str) or not action_summary.strip():
        raise ModuleError("action_summary is required and must be non-empty")
    if len(action_summary) > 500:
        raise ModuleError("action_summary limited to 500 chars")

    timeout_seconds = inputs.get("timeout_seconds", 300)
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise ModuleError("timeout_seconds must be an integer")
    if not (MIN_TIMEOUT_S <= timeout_seconds <= MAX_TIMEOUT_S):
        raise ModuleError(
            "timeout_seconds must be between %d and %d" % (MIN_TIMEOUT_S, MAX_TIMEOUT_S)
        )

    request_id = "appr_" + secrets.token_hex(6)
    expires_at = (datetime.now(timezone.utc)
                  + timedelta(seconds=timeout_seconds)).isoformat()
    key, mode = _signing_key(ctx)

    record = {
        "request_id": request_id,
        "user_id": user_id,
        "channel": channel,
        "recipient_phone": recipient_phone,
        "action_summary": action_summary,
        "status": "pending_user_action",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
        "signature_mode": mode,
    }
    record["signature"] = _sign(record, key)
    ctx.memory_set(RECORD_PREFIX + request_id, record)

    try:
        ctx.auth_get(channel + "_send")
        provider_configured = True
    except AuthMissing:
        provider_configured = False

    if provider_configured:
        delivery = {
            "channel": channel,
            "status": "queued_locally",
            "note": (
                "Approval record created and 1-tap link issued. Provider credential "
                "'%s_send' is configured; actual %s dispatch is performed by the "
                "provider integration, not claimed by this module." % (channel, channel)
            ),
        }
    else:
        delivery = {
            "channel": channel,
            "status": "not_attempted",
            "note": (
                "No message was sent. Provider credential '%s_send' is not "
                "configured — wire it (e.g. Crew C's send_%s) before dispatch "
                "is possible. The approval is still pending at the URL below." 
                % (channel, channel)
            ),
        }

    ctx.log("approval_request.created",
            {"request_id": request_id, "channel": channel,
             "provider_configured": provider_configured})
    ctx.bill(EXEC_PRICE_USD, "approval_request %s" % request_id)

    return {
        "request_id": request_id,
        "status": "pending_user_action",
        "expires_at": expires_at,
        "approval_url": "%s/%s" % (APPROVAL_URL_BASE, request_id),
        "approval_url_note": (
            "Placeholder URL — the human-facing approval endpoint is provisioned "
            "at deploy time; this request_id is the lookup key."
        ),
        "signature_mode": mode,
        "delivery": delivery,
    }
