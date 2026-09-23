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
        "account_sid": "AC123", "auth_token": "tok",
        "whatsapp_from": "+15551234567",
    })
}

INPUTS = {"to": "+15559876543", "message": "hello on whatsapp"}


def test_happy_path_sends_whatsapp(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "SMwa123", "status": "queued"}, record=seen))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "queued", "message_sid": "SMwa123"}
    form = urllib.parse.parse_qs(seen[0].data.decode())
    assert form["To"] == ["whatsapp:+15559876543"]
    assert form["From"] == ["whatsapp:+15551234567"]


def test_missing_message_rejected():
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "+15559876543"}, ctx)


def test_invalid_phone_rejected():
    ctx = FakeCtx(auth=TWILIO_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "nope", "message": "hi"}, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_send(monkeypatch):
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "SMx"}, record=called))
    ctx = FakeCtx(auth=TWILIO_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == []


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"sid": "SMwa123", "status": "queued"}))
    ctx = FakeCtx(auth=TWILIO_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "message_sid"}


def test_missing_whatsapp_from_is_module_error():
    auth = {"twilio": json.dumps({"account_sid": "AC123", "auth_token": "tok"})}
    ctx = FakeCtx(auth=auth)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
