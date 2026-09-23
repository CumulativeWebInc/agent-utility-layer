"""Tests for calc_tax. Stdlib + pytest only."""

import os
import sys

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_calc_tax", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
DISCLAIMER = _mod.DISCLAIMER
ModuleError = _mod.ModuleError
PRICE_PER_EXEC_USD = _mod.PRICE_PER_EXEC_USD
execute = _mod.execute


class FakeCtx:
    def __init__(self):
        self.approval_requests = []
        self.bills = []
        self.logs = []
        self.memory = {}

    def auth_get(self, provider):
        # AuthMissing is defined at top level via _mod
        raise AuthMissing("calc_tax needs no credential")

    def approval_request(self, summary, timeout_seconds=300):
        self.approval_requests.append(summary)
        return "apr_test_001"

    def memory_get(self, key):
        return self.memory.get(key)

    def memory_set(self, key, value):
        self.memory[key] = value

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        self.bills.append((amount_usd, memo))


def test_exclusive_tax_us_ny():
    ctx = FakeCtx()
    out = execute({"amount_cents": 10000, "jurisdiction": "US-NY"}, ctx)
    assert out["status"] == "computed"
    assert out["subtotal_cents"] == 10000
    # 10000 * 0.08875 = 887.5 -> half-up 888
    assert out["tax_total_cents"] == 888
    assert out["total_cents"] == 10888
    assert len(out["taxes"]) == 1
    assert ctx.bills == [(PRICE_PER_EXEC_USD, "calc_tax US-NY 10000")]


def test_inclusive_tax_backout():
    ctx = FakeCtx()
    out = execute({"amount_cents": 12000, "jurisdiction": "GB", "tax_inclusive": True}, ctx)
    # 12000 / 1.2 = 10000 net, 2000 VAT
    assert out["subtotal_cents"] == 10000
    assert out["tax_total_cents"] == 2000
    assert out["total_cents"] == 12000


def test_custom_jurisdiction_with_explicit_rate():
    ctx = FakeCtx()
    out = execute({"amount_cents": 10000, "jurisdiction": "CUSTOM", "tax_rate": 0.05}, ctx)
    assert out["tax_total_cents"] == 500
    assert out["total_cents"] == 10500


def test_table_override_with_explicit_rate():
    ctx = FakeCtx()
    out = execute({"amount_cents": 10000, "jurisdiction": "GB", "tax_rate": 0.10}, ctx)
    assert out["tax_total_cents"] == 1000
    assert out["taxes"][0]["label"] == "custom rate"


def test_no_auth_no_approval_needed():
    ctx = FakeCtx()
    out = execute({"amount_cents": 100, "jurisdiction": "DE"}, ctx)
    assert out["status"] == "computed"
    assert ctx.approval_requests == []


def test_disclaimer_present():
    ctx = FakeCtx()
    out = execute({"amount_cents": 100, "jurisdiction": "AU"}, ctx)
    assert out["note"] == DISCLAIMER
    assert "Not tax advice" in out["note"]


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"amount_cents": -1, "jurisdiction": "GB"},
        {"amount_cents": "100", "jurisdiction": "GB"},
        {"amount_cents": 100},  # missing jurisdiction
        {"amount_cents": 100, "jurisdiction": "XX"},  # unknown
        {"amount_cents": 100, "jurisdiction": "CUSTOM"},  # custom w/o rate
        {"amount_cents": 100, "jurisdiction": "GB", "tax_rate": 1.5},
        {"amount_cents": 100, "jurisdiction": "GB", "tax_inclusive": "yes"},
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.bills == []


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute({"amount_cents": 100, "jurisdiction": "CA"}, ctx)
    expected = {"status", "jurisdiction", "tax_inclusive", "subtotal_cents",
                "taxes", "tax_total_cents", "total_cents", "note"}
    assert set(out.keys()) == expected
