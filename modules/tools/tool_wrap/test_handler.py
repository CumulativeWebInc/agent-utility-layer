"""Tests for tool_wrap. _fetch_url is monkeypatched with FAKE responses;
nothing here touches the live network."""
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


OPENAPI_DOC = {
    "openapi": "3.0.0",
    "paths": {
        "/v1/forecast": {
            "get": {
                "operationId": "getWeatherForecast",
                "summary": "Fetches current weather and forecast by coordinates or city.",
                "parameters": [
                    {"name": "location", "in": "query", "required": True,
                     "description": "City name or ZIP code",
                     "schema": {"type": "string"}},
                    {"name": "units", "in": "query", "required": False,
                     "schema": {"type": "string"}},
                ],
            }
        }
    },
}

HTML_DOC = b"""<html><body>
<form id="signup" action="/subscribe" method="post">
<input name="email" type="email" required>
<input name="plan" type="text">
<button>Go</button>
</form></body></html>"""


def fake_openapi(url):
    return "application/json", json.dumps(OPENAPI_DOC).encode()


def fake_html(url):
    return "text/html", HTML_DOC


def fake_text(url):
    return "text/plain", b"just some text"


def test_openapi_wrap_happy_path(monkeypatch):
    monkeypatch.setattr(handler, "_fetch_url", fake_openapi)
    out = handler.execute(
        {"target_url": "https://api.weather.com/v1/forecast", "method": "GET"},
        FakeCtx(),
    )
    spec = out["openai_function_spec"]
    assert out["tool_id"].startswith("tool_")
    assert spec["name"] == "getweatherforecast"
    assert spec["parameters"]["required"] == ["location"]
    assert spec["parameters"]["properties"]["location"]["type"] == "string"
    assert out["wrap_source"] == "openapi"


def test_tool_id_deterministic():
    ctx = FakeCtx()
    import unittest.mock as mock

    with mock.patch.object(handler, "_fetch_url", fake_openapi):
        a = handler.execute({"target_url": "https://x.io/a"}, ctx)["tool_id"]
        b = handler.execute({"target_url": "https://x.io/a"}, ctx)["tool_id"]
    assert a == b


def test_tool_id_differs_by_method():
    import unittest.mock as mock

    with mock.patch.object(handler, "_fetch_url", fake_openapi):
        a = handler.execute({"target_url": "https://x.io/a", "method": "GET"},
                            FakeCtx())["tool_id"]
        b = handler.execute({"target_url": "https://x.io/a", "method": "POST"},
                            FakeCtx())["tool_id"]
    assert a != b


def test_html_form_wrap(monkeypatch):
    monkeypatch.setattr(handler, "_fetch_url", fake_html)
    out = handler.execute({"target_url": "https://example.com/signup"}, FakeCtx())
    spec = out["openai_function_spec"]
    assert "email" in spec["parameters"]["properties"]
    assert spec["parameters"]["required"] == ["email"]
    assert out["wrap_source"] == "html_form"


def test_heuristic_fallback(monkeypatch):
    monkeypatch.setattr(handler, "_fetch_url", fake_text)
    out = handler.execute({"target_url": "https://example.com/plain"}, FakeCtx())
    assert out["wrap_source"] == "heuristic_url"
    assert "example" in out["openai_function_spec"]["name"]
    assert "heuristic" in out["openai_function_spec"]["description"].lower()


def test_fetch_failure_raises_no_fake_spec(monkeypatch):
    def boom(url):
        raise handler.ModuleError("simulated network failure")

    monkeypatch.setattr(handler, "_fetch_url", boom)
    with pytest.raises(handler.ModuleError):
        handler.execute({"target_url": "https://down.example.com/"}, FakeCtx())


def test_invalid_inputs_rejected():
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute({"target_url": "not-a-url"}, ctx)
    with pytest.raises(handler.ModuleError):
        handler.execute({"target_url": "ftp://x.io/f"}, ctx)
    with pytest.raises(handler.ModuleError):
        handler.execute({"target_url": "https://x.io/", "method": "BREW"}, ctx)
    with pytest.raises(handler.ModuleError):
        handler.execute({}, ctx)


def test_auth_token_required_when_auth_type_set(monkeypatch):
    monkeypatch.setattr(handler, "_fetch_url", fake_text)
    ctx = FakeCtx()
    with pytest.raises(handler.ModuleError):
        handler.execute(
            {"target_url": "https://api.x.io/", "auth_type": "bearer"}, ctx
        )


def test_auth_token_never_returned_or_logged(monkeypatch):
    monkeypatch.setattr(handler, "_fetch_url", fake_text)
    ctx = FakeCtx()
    out = handler.execute(
        {"target_url": "https://api.x.io/", "auth_type": "bearer",
         "auth_token": "wx_live_token_123"},
        ctx,
    )
    dumped = json.dumps(out) + json.dumps(ctx.logs)
    assert "wx_live_token_123" not in dumped
    assert out["auth_type"] == "bearer"


def test_bills_one_dollar_wrap():
    import unittest.mock as mock

    ctx = FakeCtx()
    with mock.patch.object(handler, "_fetch_url", fake_text):
        handler.execute({"target_url": "https://x.io/"}, ctx)
    assert ctx.bills and ctx.bills[0]["amount_usd"] == 1.00


def test_outputs_match_schema_keys():
    import unittest.mock as mock

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "capability.json")) as f:
        schema = json.load(f)["outputs_schema"]["properties"]
    ctx = FakeCtx()
    with mock.patch.object(handler, "_fetch_url", fake_openapi):
        out = handler.execute({"target_url": "https://x.io/api"}, ctx)
    for k in ("tool_id", "openai_function_spec"):
        assert k in out and k in schema
