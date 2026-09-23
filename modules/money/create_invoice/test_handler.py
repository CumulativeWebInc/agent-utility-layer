"""Tests for create_invoice. Stdlib + pytest only."""

import os
import sys

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_create_invoice", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
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
        # AuthMissing is defined at top level via _mod
        raise AuthMissing(f"No credential for '{provider}'.")

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


def good_inputs(**kw):
    d = {
        "customer_name": "Acme Records",
        "customer_email": "billing@acme.example",
        "items": [
            {"description": "Mixing — track A", "qty": 2, "unit_cents": 15000},
            {"description": "Mastering", "qty": 1, "unit_cents": 8000},
        ],
        "tax_rate": 0.08,
        "due_date": "2026-10-23",
    }
    d.update(kw)
    return d


def test_happy_path_totals():
    ctx = FakeCtx()
    out = execute(good_inputs(), ctx)
    assert out["status"] == "issued"
    assert out["subtotal_cents"] == 38000
    assert out["tax_cents"] == 3040  # 38000 * 0.08
    assert out["total_cents"] == 41040
    assert "Acme Records" in out["html"] and "410.40" in out["html"]
    assert ctx.bills == [(PRICE_PER_EXEC_USD, f"create_invoice {out['invoice_number']}")]


def test_no_auth_no_approval_needed_for_a_document():
    ctx = FakeCtx()  # empty auth; approval never triggered
    out = execute(good_inputs(), ctx)
    assert out["status"] == "issued"
    assert ctx.approval_requests == []


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"items": [{"description": "x", "qty": 1, "unit_cents": 100}]},  # no customer
        {"customer_name": "A", "items": []},
        {"customer_name": "A", "items": [{"description": "", "qty": 1, "unit_cents": 100}]},
        {"customer_name": "A", "items": [{"description": "x", "qty": 0, "unit_cents": 100}]},
        {"customer_name": "A", "items": [{"description": "x", "qty": 1, "unit_cents": -1}]},
        {"customer_name": "A", "items": "nope"},
        {"customer_name": "A", "items": [{"description": "x", "qty": 1, "unit_cents": 100}], "tax_rate": 2},
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.bills == []


def test_auto_numbering_increments():
    ctx = FakeCtx()
    a = execute(good_inputs(), ctx)
    b = execute(good_inputs(), ctx)
    assert a["invoice_number"] != b["invoice_number"]
    assert a["invoice_number"].startswith("INV-")


def test_custom_invoice_number_respected():
    ctx = FakeCtx()
    out = execute(good_inputs(invoice_number="CUSTOM-42"), ctx)
    assert out["invoice_number"] == "CUSTOM-42"


def test_invoices_persisted_for_reports():
    ctx = FakeCtx()
    out = execute(good_inputs(), ctx)
    stored = ctx.memory_get("invoices")
    assert len(stored) == 1
    assert stored[0]["invoice_number"] == out["invoice_number"]
    assert stored[0]["total_cents"] == 41040


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute(good_inputs(), ctx)
    expected = {"status", "invoice_id", "invoice_number", "customer_name",
                "subtotal_cents", "tax_cents", "total_cents", "currency", "html"}
    assert set(out.keys()) == expected
