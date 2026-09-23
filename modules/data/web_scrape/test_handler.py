"""Tests for web_scrape handler. No live network: urlopen is monkeypatched."""

import os
import sys
import urllib.error
import urllib.request

from .handler import ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self):
        self.logs = []

    def auth_get(self, provider):
        raise AssertionError("no provider needed")

    def approval_request(self, summary, timeout_seconds=300):
        raise AssertionError("approval should not be requested")

    def memory_get(self, key):
        return None

    def memory_set(self, key, value):
        pass

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        pass


FIXTURE_HTML = b"""<!doctype html><html><head><title>Test Page</title>
<script>var x = 1;</script><style>.a{color:red}</style></head>
<body><h1>Hello</h1><p>World <b>bold</b></p>
<a href="https://example.com/a">Link A</a>
<a href="/relative">Link B</a></body></html>"""


class FakeResp:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self._body if n is None or n < 0 else self._body[:n]


def _patch(monkeypatch, body=FIXTURE_HTML):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=None: FakeResp(body)
    )


def test_happy_path_extracts_text(monkeypatch):
    _patch(monkeypatch)
    out = execute({"url": "https://example.com/page"}, FakeCtx())
    assert out["status"] == "ok"
    assert out["title"] == "Test Page"
    assert "Hello" in out["text"] and "World bold" in out["text"]
    assert "var x = 1" not in out["text"]  # script excluded
    assert ".a{color:red}" not in out["text"]  # style excluded
    assert out["link_count"] == 2
    assert out["links"][0] == {"href": "https://example.com/a", "text": "Link A"}
    assert out["truncated"] is False


def test_links_mode_omits_text(monkeypatch):
    _patch(monkeypatch)
    out = execute({"url": "https://example.com/p", "extract_mode": "links"}, FakeCtx())
    assert out["text"] == ""
    assert out["link_count"] == 2


def test_truncation_flag(monkeypatch):
    _patch(monkeypatch)
    out = execute({"url": "https://example.com/p", "max_bytes": 50}, FakeCtx())
    assert out["truncated"] is True
    assert out["fetched_bytes"] == 50


def test_invalid_urls_raise_module_error():
    ctx = FakeCtx()
    for bad in ("ftp://example.com/f", "not a url", "", "example.com/no-scheme", 123, None):
        try:
            execute({"url": bad}, ctx)
            raise AssertionError(f"expected ModuleError for {bad!r}")
        except ModuleError:
            pass


def test_bad_mode_and_timeout_raise_module_error():
    ctx = FakeCtx()
    for bad in ({"url": "https://example.com", "extract_mode": "markdown"},
                {"url": "https://example.com", "timeout_seconds": 0},
                {"url": "https://example.com", "max_bytes": -5},
                "nope"):
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {bad!r}")
        except ModuleError:
            pass


def test_network_failure_is_module_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("dns fail")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    try:
        execute({"url": "https://example.com/x"}, FakeCtx())
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "fetch failed" in str(e).lower()


def test_outputs_match_schema_keys(monkeypatch):
    _patch(monkeypatch)
    out = execute({"url": "https://example.com/x"}, FakeCtx())
    assert set(out.keys()) == {
        "status", "url", "title", "text", "char_count",
        "links", "link_count", "fetched_bytes", "truncated",
    }
    assert out["char_count"] == len(out["text"])
