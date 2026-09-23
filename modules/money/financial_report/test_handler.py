"""Tests for financial_report. Stdlib + pytest only."""

import os
import sys

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_financial_report", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
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
        raise AuthMissing("financial_report needs no credential")

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


def seed(ctx):
    ctx.memory_set("invoices", [
        {"invoice_number": "INV-1", "customer_name": "Acme", "currency": "usd",
         "total_cents": 41040, "due_date": "2026-10-23"},
        {"invoice_number": "INV-2", "customer_name": "Beta", "currency": "usd",
         "total_cents": 10000, "due_date": None},
    ])
    ctx.memory_set("expenses", [
        {"expense_id": "exp_1", "amount_cents": 4599, "category": "software",
         "vendor": "Registrar", "currency": "usd", "date": "2026-09-20"},
        {"expense_id": "exp_2", "amount_cents": 2000, "category": "ads",
         "vendor": "", "currency": "usd", "date": "2026-09-21"},
    ])


def test_happy_path_aggregates_ledgers():
    ctx = FakeCtx()
    seed(ctx)
    out = execute({"title": "Sept P&L"}, ctx)
    assert out["status"] == "generated"
    s = out["summary"]
    assert s["invoice_count"] == 2 and s["expense_count"] == 2
    assert s["invoiced_total_cents"] == 51040
    assert s["expense_total_cents"] == 6599
    assert s["net_cents"] == 44441
    assert s["by_category"] == {"software": 4599, "ads": 2000}
    assert "Sept P&amp;L" in out["html"] or "Sept P&L" in out["html"]
    assert ctx.bills == [(PRICE_PER_EXEC_USD, "financial_report Sept P&L")]


def test_empty_ledger_is_honest_zero():
    ctx = FakeCtx()
    out = execute({}, ctx)
    assert out["summary"]["net_cents"] == 0
    assert out["summary"]["invoice_count"] == 0
    assert "No invoices recorded" in out["html"]


def test_currency_filter():
    ctx = FakeCtx()
    seed(ctx)
    ctx.memory["invoices"].append(
        {"invoice_number": "INV-EU", "customer_name": "EU Co", "currency": "eur",
         "total_cents": 5000, "due_date": None})
    out = execute({"currency": "eur"}, ctx)
    assert out["summary"]["invoice_count"] == 1
    assert out["summary"]["invoiced_total_cents"] == 5000


def test_section_include_filter():
    ctx = FakeCtx()
    seed(ctx)
    out = execute({"include": ["expenses"]}, ctx)
    assert "Invoices" not in out["html"]
    assert "Expenses" in out["html"]


def test_no_auth_no_approval_needed():
    ctx = FakeCtx()
    seed(ctx)
    out = execute({}, ctx)
    assert out["status"] == "generated"
    assert ctx.approval_requests == []


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"title": "  "},
        {"currency": "USDD"},
        {"include": []},
        {"include": ["invoices", "payroll"]},
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.bills == []


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute({}, ctx)
    assert set(out.keys()) == {"status", "title", "html", "summary"}
    assert set(out["summary"].keys()) == {
        "invoice_count", "expense_count", "invoiced_total_cents",
        "expense_total_cents", "net_cents", "by_category", "generated_at"}
