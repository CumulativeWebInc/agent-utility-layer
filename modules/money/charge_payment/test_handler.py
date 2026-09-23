"""Tests for charge_payment. Stdlib + pytest only."""

import json
import sys
import os
import urllib.error

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_charge_payment", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ApprovalDenied = _mod.ApprovalDenied
AuthMissing = _mod.AuthMissing
ModuleError = _mod.ModuleError
PRICE_PER_EXEC_USD = _mod.PRICE_PER_EXEC_USD
execute = _mod.execute


class FakeCtx:
    def __init__(self, auth=None, approve=True):
        self.auth = auth or {}
        self.approve = approve
        self.approval_requests = []
        self.bills = []
        self.logs = []
        self.memory = {}

    def auth_get(self, provider):
        if provider not in self.auth:
            raise AuthMissing(
                f"No credential configured for provider '{provider}'. "
                "Add it via the spine auth flow before charging."
            )
        return self.auth[provider]

    def approval_request(self, summary, timeout_seconds=300):
        self.approval_requests.append(summary)
        if self.approve is True:
            return "apr_test_001"
        raise ApprovalDenied("Human denied the request.")

    def memory_get(self, key):
        return self.memory.get(key)

    def memory_set(self, key, value):
        self.memory[key] = value

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        self.bills.append((amount_usd, memo))


def good_inputs(**kw):
    d = {"amount_cents": 2500, "customer": "cus_test_123", "description": "Test charge"}
    d.update(kw)
    return d


def test_happy_path_simulated():
    ctx = FakeCtx()
    out = execute(good_inputs(provider="test"), ctx)
    assert out["status"] == "succeeded"
    assert out["charge_id"].startswith("ch_test_")
    assert out["simulated"] is True
    assert out["approved"] is True and out["approval_id"] == "apr_test_001"
    assert ctx.bills == [(PRICE_PER_EXEC_USD, f"charge_payment {out['charge_id']}")]
    # audit log carries no secrets
    assert any(e == "charge_payment.executed" for e, _ in ctx.logs)


def test_approval_gate_fires_before_anything():
    ctx = FakeCtx(approve=False)  # no creds configured either
    with pytest.raises(ApprovalDenied):
        execute(good_inputs(), ctx)
    assert len(ctx.approval_requests) == 1
    assert "25.00" in ctx.approval_requests[0] and "cus_test_123" in ctx.approval_requests[0]
    assert ctx.bills == []  # nothing billed on denial
    assert ctx.logs == []


def test_missing_auth_after_approval():
    ctx = FakeCtx(approve=True)  # approved, but no 'stripe' credential
    with pytest.raises(AuthMissing):
        execute(good_inputs(provider="stripe"), ctx)
    # approval gate still fired FIRST, before the AuthMissing
    assert len(ctx.approval_requests) == 1
    assert ctx.bills == []


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"amount_cents": 0, "customer": "cus_x"},
        {"amount_cents": -5, "customer": "cus_x"},
        {"amount_cents": "2500", "customer": "cus_x"},
        {"amount_cents": 2500},  # missing customer
        {"amount_cents": 2500, "customer": "   "},
        {"amount_cents": 2500, "customer": "cus_x", "currency": "USDD"},
        {"amount_cents": 2500, "customer": "cus_x", "provider": "paypal"},
        "not-a-dict",
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.approval_requests == []  # validation happens before approval


def test_real_provider_path_mocked_stripe():
    h = _mod

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"id": "pi_live_abc", "status": "succeeded"}).encode()

    def fake_urlopen(req, timeout=30):
        assert "api.stripe.com/v1/payment_intents" in req.full_url
        assert req.headers.get("Authorization") == "Bearer sk_test_FAKE"
        return FakeResp()

    real = h.urllib.request.urlopen
    h.urllib.request.urlopen = fake_urlopen
    try:
        ctx = FakeCtx(auth={"stripe": "sk_test_FAKE"})
        out = execute(good_inputs(provider="stripe"), ctx)
    finally:
        h.urllib.request.urlopen = real
    assert out["charge_id"] == "pi_live_abc"
    assert out["simulated"] is False
    # credential never leaked into logs
    assert not any("sk_test_FAKE" in str(l) for l in ctx.logs)


def test_stripe_error_surfaces_cleanly():
    h = _mod

    def fake_urlopen(req, timeout=30):
        body = json.dumps({"error": {"message": "Your card was declined."}}).encode()
        raise urllib.error.HTTPError(req.full_url, 402, "Payment Required",
                                     {"Content-Type": "application/json"}, _Body(body))

    class _Body:
        def __init__(self, b):
            self.b = b

        def read(self, *a):
            return self.b

        def close(self):
            pass

    real = h.urllib.request.urlopen
    h.urllib.request.urlopen = fake_urlopen
    try:
        ctx = FakeCtx(auth={"stripe": "sk_test_FAKE"})
        with pytest.raises(ModuleError, match="declined"):
            execute(good_inputs(provider="stripe"), ctx)
    finally:
        h.urllib.request.urlopen = real


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute(good_inputs(provider="test"), ctx)
    expected = {"status", "charge_id", "amount_cents", "currency", "provider_status",
                "simulated", "approved", "approval_id", "executed_at"}
    assert set(out.keys()) == expected
