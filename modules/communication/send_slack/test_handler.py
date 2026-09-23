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

WEBHOOK_AUTH = {"slack": json.dumps({"webhook_url": "https://hooks.slack.com/services/T/B/X"})}
BOT_AUTH = {"slack": json.dumps({"bot_token": "xoxb-fake"})}

INPUTS = {"text": "deploy complete"}


def test_happy_path_via_webhook(monkeypatch):
    seen = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        fake_urlopen_factory("ok", record=seen))
    ctx = FakeCtx(auth=WEBHOOK_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "sent", "ts": "webhook"}
    payload = json.loads(seen[0].data.decode())
    assert payload["text"] == "deploy complete"


def test_happy_path_via_bot_token(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"ok": True, "ts": "1727193600.0001"}, record=seen))
    ctx = FakeCtx(auth=BOT_AUTH)
    result = handler.execute({"text": "hi", "channel": "#general"}, ctx)
    assert result == {"status": "sent", "ts": "1727193600.0001"}
    payload = json.loads(seen[0].data.decode())
    assert payload["channel"] == "#general"


def test_missing_text_rejected():
    ctx = FakeCtx(auth=WEBHOOK_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({}, ctx)


def test_bot_token_without_channel_rejected(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        fake_urlopen_factory({"ok": True, "ts": "1"}))
    ctx = FakeCtx(auth=BOT_AUTH)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_post(monkeypatch):
    called = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        fake_urlopen_factory("ok", record=called))
    ctx = FakeCtx(auth=WEBHOOK_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == []


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen_factory("ok"))
    ctx = FakeCtx(auth=WEBHOOK_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "ts"}
