"""Tests for manage_subscription. Stdlib + pytest only."""

import os
import sys

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_manage_subscription", os.path.join(_HERE, "handler.py"))
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


def test_create_happy_path_simulated():
    ctx = FakeCtx()
    out = execute({"action": "create", "customer": "cus_1", "price": "price_1", "provider": "test"}, ctx)
    assert out["status"] == "ok" and out["state"] == "active"
    assert out["subscription_id"].startswith("sub_test_")
    assert out["approved"] is True and out["simulated"] is True
    assert len(ctx.approval_requests) == 1


def test_cancel_denied_by_human():
    ctx = FakeCtx(approve=False)
    with pytest.raises(ApprovalDenied):
        execute({"action": "cancel", "subscription_id": "sub_1", "provider": "test"}, ctx)
    assert len(ctx.approval_requests) == 1
    assert ctx.bills == [] and ctx.logs == []


def test_get_is_read_only_no_approval():
    ctx = FakeCtx()
    out = execute({"action": "get", "subscription_id": "sub_1", "provider": "test"}, ctx)
    assert out["status"] == "ok" and out["state"] == "active"
    assert out["approved"] is False and out["approval_id"] is None
    assert ctx.approval_requests == []
    assert ctx.bills == [(PRICE_PER_EXEC_USD, f"manage_subscription get {out['subscription_id']}")]


def test_update_requires_approval_and_a_change():
    ctx = FakeCtx(approve=False)
    with pytest.raises(ApprovalDenied):
        execute({"action": "update", "subscription_id": "sub_1",
                 "cancel_at_period_end": True, "provider": "test"}, ctx)
    ctx2 = FakeCtx()
    with pytest.raises(ModuleError):
        execute({"action": "update", "subscription_id": "sub_1", "provider": "test"}, ctx2)


def test_missing_auth_after_approval_on_create():
    ctx = FakeCtx(approve=True)  # approved, no 'stripe' credential
    with pytest.raises(AuthMissing):
        execute({"action": "create", "customer": "cus_1", "price": "price_1", "provider": "stripe"}, ctx)
    assert len(ctx.approval_requests) == 1
    assert ctx.bills == []


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"action": "explode", "provider": "test"},
        {"action": "create", "provider": "test"},  # missing customer/price
        {"action": "cancel", "provider": "test"},  # missing subscription_id
        {"action": "get", "subscription_id": "  ", "provider": "test"},
        {"action": "create", "customer": "c", "price": "p", "provider": "paypal"},
        {"action": "create", "customer": "c", "price": "p", "trial_days": -1, "provider": "test"},
        {"action": "update", "subscription_id": "s", "price": "p",
         "cancel_at_period_end": "yes", "provider": "test"},
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.approval_requests == []


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute({"action": "create", "customer": "cus_1", "price": "price_1", "provider": "test"}, ctx)
    expected = {"status", "subscription_id", "state", "simulated",
                "action", "approved", "approval_id", "executed_at"}
    assert set(out.keys()) == expected
