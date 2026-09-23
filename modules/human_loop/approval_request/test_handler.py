"""Tests for approval_request. FakeCtx = in-memory stand-in for the spine ctx;
fake providers are clearly labeled and never presented as live."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handler


class FakeCtx:
    """Duck-typed spine ctx for tests. FAKE — demo only."""

    def __init__(self, auth=None):
        self.mem = {}
        self.auth = dict(auth or {})
        self.bills = []
        self.logs = []

    def auth_get(self, provider):
        if provider not in self.auth:
            raise handler.AuthMissing("no credential configured for '%s'" % provider)
        return self.auth[provider]

    def approval_request(self, summary, timeout_seconds=300):
        return "appr_test"

    def memory_get(self, key):
        return self.mem.get(key)

    def memory_set(self, key, value):
        self.mem[key] = value

    def log(self, event, data=None):
        self.logs.append((event, dict(data or {})))

    def bill(self, amount_usd, memo):
        self.bills.append({"amount_usd": amount_usd, "memo": memo})


def _req(**kw):
    base = {
        "user_id": "usr_991823",
        "channel": "sms",
        "recipient_phone": "+15550192834",
        "action_summary": "Book Flight 302 to NYC for $240.00",
    }
    base.update(kw)
    return base


def test_happy_path_with_signing_key():
    ctx = FakeCtx(auth={"approval_signing_key": "test-secret"})
    out = handler.execute(_req(), ctx)
    assert out["request_id"].startswith("appr_")
    assert out["status"] == "pending_user_action"
    assert "expires_at" in out
    assert out["signature_mode"] == "configured"
    record = ctx.memory_get(handler.RECORD_PREFIX + out["request_id"])
    assert record is not None
    assert handler.verify_signature(record, "test-secret")
    assert ctx.bills[0]["amount_usd"] == 0.01


def test_ephemeral_fallback_honestly_labeled():
    ctx = FakeCtx()
    out = handler.execute(_req(), ctx)
    assert out["signature_mode"] == "local_ephemeral"
    record = ctx.memory_get(handler.RECORD_PREFIX + out["request_id"])
    key = ctx.memory_get(handler.SIGNING_KEY_STORE)
    assert handler.verify_signature(record, key)
    assert not handler.verify_signature(record, "wrong-key")


def test_tampered_record_fails_verification():
    ctx = FakeCtx(auth={"approval_signing_key": "s3cr3t"})
    out = handler.execute(_req(), ctx)
    record = ctx.memory_get(handler.RECORD_PREFIX + out["request_id"])
    record["action_summary"] = "Book Flight 302 to NYC for $24,000.00"
    assert not handler.verify_signature(record, "s3cr3t")


def test_delivery_never_claims_sent():
    ctx = FakeCtx(auth={"approval_signing_key": "k"})
    out = handler.execute(_req(channel="whatsapp"), ctx)
    assert out["delivery"]["status"] == "not_attempted"
    assert "No message was sent" in out["delivery"]["note"]


def test_delivery_queued_label_when_provider_configured():
    ctx = FakeCtx(auth={"approval_signing_key": "k", "sms_send": "cred"})
    out = handler.execute(_req(), ctx)
    assert out["delivery"]["status"] == "queued_locally"
    assert "not claimed by this module" in out["delivery"]["note"]


def test_invalid_channel_rejected():
    with pytest.raises(handler.ModuleError):
        handler.execute(_req(channel="carrier_pigeon"), FakeCtx())


def test_bad_phone_rejected():
    for bad in ("5550192834", "+1", "+15550192834567890123", 12345):
        with pytest.raises(handler.ModuleError):
            handler.execute(_req(recipient_phone=bad), FakeCtx())


def test_missing_or_long_summary_rejected():
    with pytest.raises(handler.ModuleError):
        handler.execute(_req(action_summary=""), FakeCtx())
    with pytest.raises(handler.ModuleError):
        handler.execute(_req(action_summary="x" * 501), FakeCtx())


def test_timeout_bounds():
    with pytest.raises(handler.ModuleError):
        handler.execute(_req(timeout_seconds=5), FakeCtx())
    with pytest.raises(handler.ModuleError):
        handler.execute(_req(timeout_seconds=999999), FakeCtx())
    ctx = FakeCtx()
    out = handler.execute(_req(timeout_seconds=3600), ctx)
    assert out["status"] == "pending_user_action"


def test_outputs_match_schema_keys():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "capability.json")) as f:
        schema = json.load(f)["outputs_schema"]["properties"]
    ctx = FakeCtx(auth={"approval_signing_key": "k"})
    out = handler.execute(_req(), ctx)
    for k in ("request_id", "status", "expires_at"):
        assert k in out and k in schema
