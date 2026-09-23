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

PUSH_AUTH = {"push": json.dumps({
    "endpoint_url": "https://push.example.com/v1/send",
    "api_key": "pk-fake",
    "auth_scheme": "Bearer",
})}

INPUTS = {"target": "device-abc", "title": "Alert", "body": "something happened"}


def test_happy_path_delivers_push(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"id": "rcpt-1"}, record=seen))
    ctx = FakeCtx(auth=PUSH_AUTH)
    result = handler.execute(dict(INPUTS), ctx)
    assert result == {"status": "sent", "receipt": "rcpt-1"}
    payload = json.loads(seen[0].data.decode())
    assert payload["target"] == "device-abc"
    assert seen[0].get_header("Authorization") == "Bearer pk-fake"


def test_missing_title_rejected():
    ctx = FakeCtx(auth=PUSH_AUTH)
    with pytest.raises(ModuleError):
        handler.execute({"target": "t", "body": "b"}, ctx)


def test_unknown_input_rejected():
    ctx = FakeCtx(auth=PUSH_AUTH)
    bad = dict(INPUTS); bad["bogus"] = 1
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_missing_credential_raises_auth_missing():
    ctx = FakeCtx(auth={})
    with pytest.raises(AuthMissing):
        handler.execute(dict(INPUTS), ctx)


def test_approval_denied_blocks_send(monkeypatch):
    called = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        fake_urlopen_factory({"id": "r"}, record=called))
    ctx = FakeCtx(auth=PUSH_AUTH, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute(dict(INPUTS), ctx)
    assert called == []


def test_output_schema_keys(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        fake_urlopen_factory({"id": "rcpt-1"}))
    ctx = FakeCtx(auth=PUSH_AUTH)
    assert set(handler.execute(dict(INPUTS), ctx).keys()) == {"status", "receipt"}


def test_missing_api_key_is_module_error():
    auth = {"push": json.dumps({"endpoint_url": "https://push.example.com/v1/send"})}
    ctx = FakeCtx(auth=auth)
    with pytest.raises(ModuleError):
        handler.execute(dict(INPUTS), ctx)
