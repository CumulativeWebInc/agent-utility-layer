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

INPUTS = {
    "document_name": "NDA v3",
    "document_text": "You agree to keep secrets.",
    "signer_name": "Jane Doe",
    "signer_email": "jane@example.com",
}


@pytest.fixture(autouse=True)
def _fake_smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)


def test_happy_path_sends_signature_request():
    ctx = FakeCtx(auth=SMTP_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result["status"] == "sent"
    assert result["request_id"].startswith("sigreq_")
    assert result["sent_to"] == "jane@example.com"
    assert len(FakeSMTP.sent) == 1
    stored = ctx.memory_get("human_signature:%s" % result["request_id"])
    assert stored["status"] == "requested"


def test_missing_signer_email_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    bad = dict(INPUTS); del bad["signer_email"]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_invalid_signer_email_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    bad = dict(INPUTS); bad["signer_email"] = "jane-at-example"
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_request():
    ctx = FakeCtx(auth=SMTP_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert FakeSMTP.sent == []


def test_output_schema_keys():
    ctx = FakeCtx(auth=SMTP_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert set(result.keys()) == {"status", "request_id", "sent_to"}
