"""Tests for the template_demo reference module (stdlib + pytest)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "spine"))

import handler  # noqa: E402
from handler import ApprovalDenied, AuthMissing, ModuleError  # noqa: E402


class FakeCtx:
    """Duck-typed ctx per CONTRACT.md."""

    def __init__(self, demo=False, creds=None, approve=True):
        self.demo = demo
        self._creds = creds or {}
        self._approve = approve
        self._memory = {}
        self.events = []
        self.bills = []

    def auth_get(self, provider):
        if provider in self._creds:
            return self._creds[provider]
        raise AuthMissing(f"no credential for {provider}")

    def approval_request(self, summary, timeout_seconds=300):
        if self._approve:
            return "appr_test_1"
        raise ApprovalDenied("denied in test")

    def memory_get(self, key):
        return self._memory.get(key)

    def memory_set(self, key, value):
        self._memory[key] = value

    def log(self, event, data):
        self.events.append((event, data))

    def bill(self, amount_usd, memo):
        self.bills.append((amount_usd, memo))
        return {"amount_usd": amount_usd}


def test_demo_happy_path():
    out = handler.execute({"message": "hello"}, FakeCtx(demo=True))
    assert out["status"] == "ok"
    assert out["echo"] == "hello"
    assert out["demo"] is True and out["simulated"] is True


def test_demo_uppercase():
    out = handler.execute({"message": "hello", "uppercase": True}, FakeCtx(demo=True))
    assert out["echo"] == "HELLO"


def test_real_happy_path_with_credential():
    ctx = FakeCtx(demo=False, creds={"template_provider": "sekret"})
    out = handler.execute({"message": "hi"}, ctx)
    assert out["demo"] is False and out["simulated"] is True
    assert any(e[0] == "template_demo.echo" for e in ctx.events)


def test_invalid_inputs_missing_message():
    with pytest.raises(ModuleError):
        handler.execute({}, FakeCtx(demo=True))


def test_invalid_inputs_wrong_type():
    with pytest.raises(ModuleError):
        handler.execute({"message": 123}, FakeCtx(demo=True))


def test_missing_credential_raises_auth_missing():
    with pytest.raises(AuthMissing):
        handler.execute({"message": "hi"}, FakeCtx(demo=False, creds={}))


def test_destructive_denied_raises_approval_denied():
    ctx = FakeCtx(demo=False, creds={"template_provider": "x"}, approve=False)
    with pytest.raises(ApprovalDenied):
        handler.execute({"message": "hi", "destructive": True}, ctx)


def test_destructive_approved_runs():
    ctx = FakeCtx(demo=False, creds={"template_provider": "x"}, approve=True)
    out = handler.execute({"message": "hi", "destructive": True}, ctx)
    assert out["status"] == "ok"
    assert any(e[0] == "template_demo.approved" for e in ctx.events)


def test_outputs_match_schema_keys():
    import json
    with open(os.path.join(os.path.dirname(__file__), "capability.json")) as fh:
        schema = json.load(fh)["outputs_schema"]["properties"]
    out = handler.execute({"message": "x"}, FakeCtx(demo=True))
    assert set(out.keys()) == set(schema.keys())
