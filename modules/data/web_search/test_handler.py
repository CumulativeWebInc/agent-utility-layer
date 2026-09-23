"""Tests for web_search handler. No live network: urlopen is monkeypatched."""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handler import AuthMissing, ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self, creds=None):
        self.creds = creds or {}
        self.logs = []
        self.bills = []
        self.store = {}

    def auth_get(self, provider):
        if provider not in self.creds:
            raise AuthMissing(f"no credential for '{provider}'")
        return self.creds[provider]

    def approval_request(self, summary, timeout_seconds=300):
        raise AssertionError("approval should not be requested")

    def memory_get(self, key):
        return self.store.get(key)

    def memory_set(self, key, value):
        self.store[key] = value

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        self.bills.append((amount_usd, memo))


class FakeResp:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


TAVILY_BODY = json.dumps({
    "results": [
        {"title": "T1", "url": "https://example.com/1", "content": "snippet one"},
        {"title": "T2", "url": "https://example.com/2", "content": "snippet two"},
    ]
})
SERPER_BODY = json.dumps({
    "organic": [{"title": "S1", "link": "https://example.com/s", "snippet": "serp snip"}]
})
BRAVE_BODY = json.dumps({
    "web": {"results": [{"title": "B1", "url": "https://example.com/b", "description": "brave snip"}]}
})


def _patch(monkeypatch, body):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp(body))


def test_happy_path_tavily(monkeypatch):
    _patch(monkeypatch, TAVILY_BODY)
    ctx = FakeCtx({"tavily": "k"})
    out = execute({"query": "agent infra"}, ctx)
    assert out["status"] == "ok"
    assert out["provider"] == "tavily"
    assert out["query_used"] == "agent infra"
    assert out["result_count"] == 2
    assert out["results"][0]["url"] == "https://example.com/1"
    assert out["results"][0]["snippet"] == "snippet one"
    assert ctx.logs and ctx.logs[0][0] == "web_search"


def test_query_builder_site_and_exclude(monkeypatch):
    seen = {}

    def fake(req, timeout=None):
        seen["url"] = req.full_url if hasattr(req, "full_url") else req.get_full_url()
        seen["data"] = req.data.decode("utf-8")
        return FakeResp(TAVILY_BODY)

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    ctx = FakeCtx({"tavily": "k"})
    out = execute({"query": "x402", "site": "example.com", "exclude": ["spam"]}, ctx)
    payload = json.loads(seen["data"])
    assert payload["query"] == "site:example.com x402 -spam"
    assert out["query_used"] == "site:example.com x402 -spam"


def test_serper_and_brave_adapters(monkeypatch):
    _patch(monkeypatch, SERPER_BODY)
    out = execute({"query": "q", "provider": "serper"}, FakeCtx({"serper": "k"}))
    assert out["results"][0]["url"] == "https://example.com/s"
    _patch(monkeypatch, BRAVE_BODY)
    out = execute({"query": "q", "provider": "brave"}, FakeCtx({"brave": "k"}))
    assert out["results"][0]["snippet"] == "brave snip"


def test_missing_key_raises_auth_missing():
    ctx = FakeCtx({})
    try:
        execute({"query": "hello"}, ctx)
        raise AssertionError("expected AuthMissing")
    except AuthMissing as e:
        assert "tavily" in str(e).lower() or "api key" in str(e).lower()


def test_empty_key_raises_auth_missing():
    try:
        execute({"query": "hello"}, FakeCtx({"tavily": "  "}))
        raise AssertionError("expected AuthMissing")
    except AuthMissing:
        pass


def test_bad_inputs_raise_module_error():
    ctx = FakeCtx({"tavily": "k"})
    for bad in ({"query": ""}, {"query": "x", "max_results": 0},
                {"query": "x", "max_results": 51}, {"query": "x", "provider": "nope"},
                {"query": "x", "timeout_seconds": -1}, "not-a-dict"):
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {bad!r}")
        except ModuleError:
            pass


def test_provider_http_failure_is_module_error(monkeypatch):
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.URLError("conn refused")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    try:
        execute({"query": "q"}, FakeCtx({"tavily": "k"}))
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "failed" in str(e).lower()


def test_unparsable_response_is_module_error(monkeypatch):
    _patch(monkeypatch, "this is not json {{{")
    try:
        execute({"query": "q"}, FakeCtx({"tavily": "k"}))
        raise AssertionError("expected ModuleError")
    except ModuleError:
        pass


def test_outputs_match_schema_keys(monkeypatch):
    _patch(monkeypatch, TAVILY_BODY)
    out = execute({"query": "q"}, FakeCtx({"tavily": "k"}))
    assert set(out.keys()) == {"status", "query_used", "provider", "results", "result_count"}
    r = out["results"][0]
    assert set(r.keys()) == {"title", "url", "snippet"}
