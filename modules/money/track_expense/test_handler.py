"""Tests for track_expense. Stdlib + pytest only."""

import os
import sys

import pytest

import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "handler_track_expense", os.path.join(_HERE, "handler.py"))
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
        raise AuthMissing("track_expense needs no credential")

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


def test_add_happy_path():
    ctx = FakeCtx()
    out = execute({"action": "add", "amount_cents": 4599, "category": "Software",
                   "vendor": "Domain registrar", "note": "renewal"}, ctx)
    assert out["status"] == "recorded"
    exp = out["expense"]
    assert exp["expense_id"].startswith("exp_")
    assert exp["amount_cents"] == 4599 and exp["category"] == "software"
    assert ctx.bills == [(PRICE_PER_EXEC_USD, f"track_expense add {exp['expense_id']}")]


def test_list_returns_recorded_expenses():
    ctx = FakeCtx()
    execute({"action": "add", "amount_cents": 100, "category": "ads"}, ctx)
    execute({"action": "add", "amount_cents": 200, "category": "ads"}, ctx)
    out = execute({"action": "list"}, ctx)
    assert out["count"] == 2 and len(out["expenses"]) == 2


def test_list_category_filter():
    ctx = FakeCtx()
    execute({"action": "add", "amount_cents": 100, "category": "ads"}, ctx)
    execute({"action": "add", "amount_cents": 200, "category": "travel"}, ctx)
    out = execute({"action": "list", "category": "travel"}, ctx)
    assert out["count"] == 1
    assert out["expenses"][0]["category"] == "travel"


def test_summary_totals_and_by_category():
    ctx = FakeCtx()
    execute({"action": "add", "amount_cents": 100, "category": "ads"}, ctx)
    execute({"action": "add", "amount_cents": 250, "category": "ads"}, ctx)
    execute({"action": "add", "amount_cents": 400, "category": "travel"}, ctx)
    out = execute({"action": "summary"}, ctx)
    assert out["count"] == 3
    assert out["total_cents"] == 750
    assert out["by_category"] == {"ads": 350, "travel": 400}


def test_no_auth_no_approval_needed():
    ctx = FakeCtx()
    out = execute({"action": "add", "amount_cents": 50, "category": "misc"}, ctx)
    assert out["status"] == "recorded"
    assert ctx.approval_requests == []


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    for bad in [
        {"action": "add"},  # missing amount
        {"action": "add", "amount_cents": 0, "category": "x"},
        {"action": "add", "amount_cents": -5, "category": "x"},
        {"action": "add", "amount_cents": "50", "category": "x"},
        {"action": "add", "amount_cents": 50, "category": "  "},
        {"action": "add", "amount_cents": 50, "date": "23-09-2026"},
        {"action": "delete"},
    ]:
        with pytest.raises(ModuleError):
            execute(bad, ctx)
    assert ctx.bills == []


def test_outputs_match_schema_keys():
    ctx = FakeCtx()
    out = execute({"action": "add", "amount_cents": 10, "category": "x"}, ctx)
    assert set(out.keys()) == {"status", "action", "expense"}
