import json
import os
import sys

import pytest

import smtplib

import importlib.util as _ilu

_handler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_spec = _ilu.spec_from_file_location("handler_under_test", _handler_path)
handler = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(handler)
from common import FakeCtx, FakeSMTP, ModuleError, AuthMissing, ApprovalDenied

SMTP_AUTH = {
    "smtp": json.dumps({
        "host": "smtp.example.com", "port": 587,
        "username": "bot", "password": "secret",
        "from_addr": "bot@example.com", "use_tls": True,
    })
}

INPUTS = {"to": "a@example.com", "subject": "Hi", "body": "hello world"}


@pytest.fixture(autouse=True)
def _fake_smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)


def test_happy_path_sends_email():
    ctx = FakeCtx(auth=SMTP_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result["status"] == "sent"
    assert result["message_id"].startswith("<")
    assert len(FakeSMTP.sent) == 1
    assert FakeSMTP.sent[0]["To"] == "a@example.com"
    assert ctx.bills and ctx.bills[0][0] == 0.001
    assert ctx.approvals, "approval must be requested before an external send"


def test_missing_required_input():
    ctx = FakeCtx(auth=SMTP_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "a@example.com", "subject": "Hi"}, ctx)


def test_invalid_email_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"to": "not-an-email", "subject": "Hi", "body": "x"}, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing) as exc:
        handler.execute(dict(INPUTS), ctx)
    assert "smtp" in str(exc.value).lower()


def test_approval_denied_blocks_send():
    ctx = FakeCtx(auth=SMTP_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert FakeSMTP.sent == [], "nothing may be sent after a denied approval"


def test_output_schema_keys():
    ctx = FakeCtx(auth=SMTP_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert set(result.keys()) == {"status", "message_id"}


def test_smtp_failure_surfaces_as_module_error(monkeypatch):
    class BoomSMTP(FakeSMTP):
        def send_message(self, msg):
            raise smtplib.SMTPException("relay refused")
    monkeypatch.setattr(smtplib, "SMTP", BoomSMTP)
    ctx = FakeCtx(auth=SMTP_AUTH)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
