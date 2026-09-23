import json
import os
import sys
import urllib.parse
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

INPUTS = {"to": "+15559876543", "text": "Your order is ready"}


def test_happy_path_places_call(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "CAabc123", "status": "queued"}, record=seen))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "queued", "call_sid": "CAabc123"}
    assert "/Calls.json" in seen[0].full_url
    form = urllib.parse.parse_qs(seen[0].data.decode())
    assert "Your order is ready" in form["Twiml"][0]  # TwiML carries the text


def test_missing_text_rejected():
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "+15559876543"}, ctx)


def test_invalid_phone_rejected():
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "xyz", "text": "hi"}, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_call(monkeypatch):
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "CAx"}, record=called))
    ctx = FakeCtx(auth=TWILIO_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == []


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "CAabc123", "status": "queued"}))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "call_sid"}


def test_call_failure_without_sid_is_module_error(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"code": 21212, "message": "Invalid From number"}))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
