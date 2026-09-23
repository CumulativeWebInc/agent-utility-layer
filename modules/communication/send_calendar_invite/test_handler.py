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
    "attendees": ["a@example.com", "b@example.com"],
    "title": "Sync call",
    "start": "2026-10-01T15:00:00Z",
    "end": "2026-10-01T15:30:00Z",
    "description": "weekly sync",
    "location": "virtual",
}


@pytest.fixture(autouse=True)
def _fake_smtp(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)


def test_happy_path_sends_invite_with_ics():
    ctx = FakeCtx(auth=SMTP_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result["status"] == "sent"
    assert result["invites_sent"] == 2
    assert result["ics_uid"]
    msg = FakeSMTP.sent[0]
    ics_parts = [p for p in msg.iter_attachments()
                 if p.get_content_type() == "text/calendar"]
    assert len(ics_parts) == 1
    ics = ics_parts[0].get_content()
    assert "BEGIN:VEVENT" in ics
    assert "DTSTART:20261001T150000Z" in ics
    assert "mailto:a@example.com" in ics


def test_missing_attendees_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    bad = dict(INPUTS); del bad["attendees"]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_bad_attendee_email_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    bad = dict(INPUTS); bad["attendees"] = ["not-an-email"]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_bad_datetime_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    bad = dict(INPUTS); bad["start"] = "yesterday-ish"
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_end_before_start_rejected():
    ctx = FakeCtx(auth=SMTP_AUTH)
    bad = dict(INPUTS)
    bad["start"], bad["end"] = bad["end"], bad["start"]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_send():
    ctx = FakeCtx(auth=SMTP_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert FakeSMTP.sent == []


def test_output_schema_keys():
    ctx = FakeCtx(auth=SMTP_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert set(result.keys()) == {"status", "invites_sent", "ics_uid"}
