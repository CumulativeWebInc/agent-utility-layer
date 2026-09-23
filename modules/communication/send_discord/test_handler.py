import json
import os
import sys
import urllib.error
import urllib.request

import pytest

import importlib.util as _ilu

_handler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_spec = _ilu.spec_from_file_location("handler_under_test", _handler_path)
handler = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(handler)
from common import FakeCtx, fake_urlopen_factory, ModuleError, AuthMissing, ApprovalDenied

DISCORD_AUTH = {"discord": json.dumps({"webhook_url": "https://discord.com/api/webhooks/1/abc"})}

INPUTS = {"message": "hello discord"}


def test_happy_path_posts_message(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"id": "123456789"}, record=seen))
    ctx = FakeCtx(auth=DISCORD_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "sent", "message_id": "123456789"}
    payload = json.loads(seen[0].data.decode())
    assert payload["content"] == "hello discord"
    assert "wait=true" in seen[0].full_url


def test_missing_message_rejected():
    ctx = FakeCtx(auth=DISCORD_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({}, ctx)


def test_empty_message_rejected():
    ctx = FakeCtx(auth=DISCORD_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"message": "   "}, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_post(monkeypatch):
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"id": "1"}, record=called))
    ctx = FakeCtx(auth=DISCORD_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == []


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        fake_urlopen_factory({"id": "123456789"}))
    ctx = FakeCtx(auth=DISCORD_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "message_id"}


def test_webhook_failure_is_module_error(monkeypatch):
    def boom(request, timeout=None):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    ctx = FakeCtx(auth=DISCORD_AUTH)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
