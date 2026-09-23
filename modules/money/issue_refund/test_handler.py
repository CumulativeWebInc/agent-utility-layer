"""Tests for issue_refund. Stdlib + pytest only."""

import json
import os
import sys

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_issue_refund", os.path.join(_HERE, "handler.py"))
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
                "Add it via the spine auth flow first."
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


def test_happy_path_simulated_full_refund():
    ctx = FakeCtx()
    out = execute({"charge_id": "ch_1", "provider": "test"}, ctx)
    assert out["status"] == "succeeded"
    assert out["refund_id"].startswith("re_test_")
    assert out["simulated"] is True and out["approved"] is True
    assert ctx.bills == [(PRICE_PER_EXEC_USD, f"issue_refund {out['refund_id']}")]


def test_partial_refund_amount_reported():
    ctx = FakeCtx()
    out = execute({"charge_id": "ch_1", "amount_cents": 1200, "provider": "test"}, ctx)
    assert out["amount_cents"] == 1200
    assert "12.00" in ctx.approval_requests[0]


def test_approval_gate_fires_and_denial_blocks():
    ctx = FakeCtx(approve=False)
    with pytest.raises(ApprovalDenied):
        execute({"charge_id": "ch_1", "provider": "test"}, ctx)
    assert len(ctx.approval_requests) == 1
    assert "ch_1" in ctx.approval_requests[0]
    assert ctx.bills == [] and ctx.logs == []


def test_missing_auth_after_approval():
    ctx = FakeCtx(approve=True)  # approved, no 'stripe' credential
    with pytest.raises(AuthMissing):
        execute({"charge_id": "ch_1", "provider": "stripe"}, ctx)
    assert len(ctx.approval_requests) == 1
    assert ctx.bills == []


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"provider": "test"},  # missing charge_id
        {"charge_id": "  ", "provider": "test"},
        {"charge_id": "ch_1", "amount_cents": 0, "provider": "test"},
        {"charge_id": "ch_1", "amount_cents": -3, "provider": "test"},
        {"charge_id": "ch_1", "provider": "square"},
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.approval_requests == []


def test_real_provider_path_mocked_stripe():
    h = _mod

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"id": "re_live_9", "status": "succeeded", "amount": 2500}).encode()

        def close(self):
            pass

    def fake_urlopen(req, timeout=30):
        assert "api.stripe.com/v1/refunds" in req.full_url
        assert req.headers.get("Authorization") == "Bearer sk_test_FAKE"
        return FakeResp()

    real = h.urllib.request.urlopen
    h.urllib.request.urlopen = fake_urlopen
    try:
        ctx = FakeCtx(auth={"stripe": "sk_test_FAKE"})
        out = execute({"charge_id": "ch_live_1", "amount_cents": 2500, "provider": "stripe"}, ctx)
    finally:
        h.urllib.request.urlopen = real
    assert out["refund_id"] == "re_live_9" and out["amount_cents"] == 2500
    assert out["simulated"] is False
    assert not any("sk_test_FAKE" in str(l) for l in ctx.logs)


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute({"charge_id": "ch_1", "provider": "test"}, ctx)
    expected = {"status", "refund_id", "charge_id", "amount_cents", "provider_status",
                "simulated", "approved", "approval_id", "executed_at"}
    assert set(out.keys()) == expected
