"""Tests for spine/billing.py (stdlib + pytest)."""

import json

import pytest

from billing import (
    APPROVAL_PRICE_USD,
    EXEC_PRICE_USD,
    SETUP_PRICE_USD,
    entry_count,
    record,
    total_for,
    totals_by_capability,
)


def test_pricing_constants():
    assert SETUP_PRICE_USD == 1.00
    assert EXEC_PRICE_USD == 0.001
    assert APPROVAL_PRICE_USD == 0.01


def test_record_appends_jsonl(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    entry = record("fp123", "template_demo", "exec", 0.001, "t", path=path)
    assert entry["agent_id"] == "fp123"
    assert entry["kind"] == "exec"
    lines = open(path).read().strip().split("\n")
    assert len(lines) == 1 and json.loads(lines[0])["id"] == entry["id"]


def test_record_rejects_bad_kind(tmp_path):
    with pytest.raises(ValueError):
        record("fp", "cap", "nope", 1.0, path=str(tmp_path / "l.jsonl"))


def test_totals(tmp_path):
    path = str(tmp_path / "l.jsonl")
    record("a1", "cap_x", "exec", 0.001, path=path)
    record("a1", "cap_x", "exec", 0.001, path=path)
    record("a1", "cap_y", "approval", 0.01, path=path)
    record("a2", "cap_x", "exec", 0.001, path=path)
    assert total_for("a1", path=path) == pytest.approx(0.012)
    assert total_for("a2", path=path) == pytest.approx(0.001)
    assert total_for("nobody", path=path) == 0.0
    by_cap = totals_by_capability("a1", path=path)
    assert by_cap == {"cap_x": pytest.approx(0.002), "cap_y": pytest.approx(0.01)}
    assert entry_count(path=path) == 4


def test_missing_ledger_is_zero(tmp_path):
    path = str(tmp_path / "never.jsonl")
    assert total_for("a", path=path) == 0.0
    assert entry_count(path=path) == 0
