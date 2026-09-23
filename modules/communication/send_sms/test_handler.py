import json
import os
import sys
import urllib.request

import pytest

import importlib.util as _ilu

_handler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_spec = _ilu.spec_from_file_location("handler_under_test", _handler_path)
handler = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(handler)
from common import FakeCtx, fake_urlopen_factory, ModuleError, AuthMissing, ApprovalDenied

TWILIO_AUTH = {
    "twilio": json.dumps({
        "account_sid": "AC123", "auth_token": "tok", "from_number": "+15551234567",
    })
}

INPUTS = {"to": "+15559876543", "message": "hello from CWI"}


def test_happy_path_queues_sms(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "SMabc123", "status": "queued"}, record=seen))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "queued", "message_sid": "SMabc123"}
    assert len(seen) == 1
    assert "api.twilio.com" in seen[0].full_url
    assert ctx.bills[0][0] == 0.001


def test_missing_required_input():
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "+15559876543"}, ctx)


def test_invalid_phone_rejected():
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "abc", "message": "hi"}, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_send(monkeypatch):
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "SMx", "status": "queued"}, record=called))
    ctx = FakeCtx(auth=TWILIO_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == [], "no provider call after denied approval"


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "SMabc123", "status": "queued"}))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "message_sid"}


def test_provider_error_without_sid_is_module_error(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"code": 21211, "message": "Invalid To number"}))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
