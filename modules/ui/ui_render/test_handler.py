"""Tests for ui_render. FakeCtx = in-memory stand-in for the spine ctx;
fake providers are clearly labeled and never presented as live."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handler


class FakeCtx:
    """Duck-typed spine ctx for tests. FAKE — demo only."""

    def __init__(self):
        self.mem = {}
        self.bills = []
        self.logs = []

    def auth_get(self, provider):
        raise handler.AuthMissing("no credential configured for '%s'" % provider)

    def approval_request(self, summary, timeout_seconds=300):
        return "appr_test"

    def memory_get(self, key):
        return self.mem.get(key)

    def memory_set(self, key, value):
        self.mem[key] = value

    def log(self, event, data=None):
        self.logs.append((event, dict(data or {})))

    def bill(self, amount_usd, memo):
        self.bills.append({"amount_usd": amount_usd, "memo": memo})


def _render(ctx, **kw):
    return handler.execute({"component_type": "data_table", "data": []} | kw, ctx)


def test_data_table_happy_path():
    ctx = FakeCtx()
    out = handler.execute(
        {"component_type": "data_table", "title": "Quarterly Earnings",
         "data": [{"Quarter": "Q1", "Revenue": 12000},
                  {"Quarter": "Q2", "Revenue": 19500}]},
        ctx,
    )
    assert out["render_id"].startswith("ui_")
    assert out["embed_url"].endswith(out["render_id"] + ".html")
    assert "iframe" in out["iframe_snippet"]
    page = ctx.memory_get(handler.RECORD_PREFIX + out["render_id"])
    assert "<table>" in page and "19500" in page and "Quarterly Earnings" in page


def test_xss_escaped():
    ctx = FakeCtx()
    out = handler.execute(
        {"component_type": "data_table",
         "data": [{"name": "<script>alert(1)</script>"}]},
        ctx,
    )
    page = ctx.memory_get(handler.RECORD_PREFIX + out["render_id"])
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_chart_renders_svg_bars():
    ctx = FakeCtx()
    out = handler.execute(
        {"component_type": "chart", "title": "Revenue",
         "data": [{"Quarter": "Q1", "Revenue": 12000},
                  {"Quarter": "Q2", "Revenue": 19500}]},
        ctx,
    )
    page = ctx.memory_get(handler.RECORD_PREFIX + out["render_id"])
    assert "<svg" in page and page.count("<rect") == 2


def test_chart_without_numeric_field_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute(
            {"component_type": "chart",
             "data": [{"a": "x"}, {"a": "y"}]},
            ctx,
        )


def test_form_renders_inputs():
    ctx = FakeCtx()
    out = handler.execute(
        {"component_type": "form", "title": "Contact",
         "data": {"email": {"type": "email", "label": "Email", "required": True},
                  "name": {"type": "text", "label": "Name"}}},
        ctx,
    )
    page = ctx.memory_get(handler.RECORD_PREFIX + out["render_id"])
    assert 'name="email"' in page and 'type="email"' in page and "required" in page


def test_form_from_field_name_list():
    ctx = FakeCtx()
    out = handler.execute(
        {"component_type": "form", "data": ["city", "zip"]}, ctx)
    page = ctx.memory_get(handler.RECORD_PREFIX + out["render_id"])
    assert 'name="city"' in page and 'name="zip"' in page


def test_confirmation_card_happy_path():
    ctx = FakeCtx()
    out = handler.execute(
        {"component_type": "confirmation_card", "title": "Confirm booking",
         "data": {"Flight": "302 to NYC", "Price": "$240.00"}},
        ctx,
    )
    page = ctx.memory_get(handler.RECORD_PREFIX + out["render_id"])
    assert "Confirm" in page and "$240.00" in page


def test_invalid_component_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute({"component_type": "video", "data": []}, ctx)


def test_missing_or_oversized_data_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute({"component_type": "data_table"}, ctx)
    with pytest.raises(handler.ModuleError):
        handler.execute(
            {"component_type": "data_table",
             "data": [{"row": i} for i in range(501)]},
            ctx,
        )


def test_render_id_deterministic():
    ctx = FakeCtx()
    payload = {"component_type": "data_table",
               "data": [{"a": 1}]}
    assert handler.execute(payload, ctx)["render_id"] == \
        handler.execute(payload, FakeCtx())["render_id"]


def test_bills_exec_price():
    ctx = FakeCtx()
    handler.execute({"component_type": "data_table", "data": [{"a": 1}]}, ctx)
    assert ctx.bills and ctx.bills[0]["amount_usd"] == 0.001


def test_outputs_match_schema_keys():
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "capability.json")) as f:
        schema = json.load(f)["outputs_schema"]["properties"]
    ctx = FakeCtx()
    out = handler.execute({"component_type": "data_table", "data": [{"a": 1}]}, ctx)
    for k in ("render_id", "embed_url", "iframe_snippet"):
        assert k in out and k in schema
