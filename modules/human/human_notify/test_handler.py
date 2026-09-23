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

NOTIFY_AUTH = {"notify": json.dumps({"webhook_url": "https://hooks.example.com/notify"})}

INPUTS = {"recipient": "ops-lead", "title": "Deploy done", "message": "v2 shipped", "channel": "push"}


def test_happy_path_notifies_human(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"id": "n-1"}, record=seen))
    ctx = FakeCtx(auth=NOTIFY_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "sent", "notification_id": "n-1"}
    payload = json.loads(seen[0].data.decode())
    assert payload["recipient"] == "ops-lead"
    assert payload["channel"] == "push"
    assert ctx.bills[0][0] == 0.01, "human-loop modules price the approval push"


def test_missing_recipient_rejected():
    ctx = FakeCtx(auth=NOTIFY_AUTH)
    bad = dict(INPUTS); del bad["recipient"]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_bad_channel_rejected():
    ctx = FakeCtx(auth=NOTIFY_AUTH)
    bad = dict(INPUTS); bad["channel"] = "smoke-signal"
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing) as exc:
        handler.execute(dict(INPUTS), ctx)
    assert "notify" in str(exc.value).lower()


def test_approval_denied_blocks_notify(monkeypatch):
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"id": "n-1"}, record=called))
    ctx = FakeCtx(auth=NOTIFY_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == []


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        fake_urlopen_factory({"id": "n-1"}))
    ctx = FakeCtx(auth=NOTIFY_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "notification_id"}


def test_webhook_failure_is_module_error(monkeypatch):
    def boom(request, timeout=None):
        raise ConnectionError("down")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    ctx = FakeCtx(auth=NOTIFY_AUTH)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
