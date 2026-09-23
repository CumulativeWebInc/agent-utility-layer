"""Tests for page_interact. Local fixture server — no live network."""
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied

PAGE = b"""<html><head><title>Test Page</title>
<meta name="description" content="a test page"></head>
<body><h1>Hello</h1><h2>World</h2>
<a href="/about">About us</a>
<form name="login" action="/login" method="post">
<input type="text" name="user"><input type="password" name="pw">
<input type="hidden" name="tok" value="abc"></form>
<p>Some visible text here.</p></body></html>"""


class FakeCtx:
    def __init__(self, approve=True, auth=None):
        self._approve = approve
        self._auth = auth or {}
        self._mem = {}
        self.logs = []
        self.bills = []
        self.approvals = []

    def auth_get(self, provider):
        if provider not in self._auth:
            raise AuthMissing(f"no credential for '{provider}'")
        return self._auth[provider]

    def approval_request(self, summary, timeout_seconds=300):
        self.approvals.append(summary)
        if not self._approve:
            raise ApprovalDenied("denied: " + summary)
        return "appr_1"

    def memory_get(self, key):
        return self._mem.get(key)

    def memory_set(self, key, value):
        self._mem[key] = value

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        self.bills.append((amount_usd, memo))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/binary":
            body, ctype = b"\x00\x01\x02", "application/octet-stream"
        else:
            body, ctype = PAGE, "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def make_server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def base():
    srv = make_server()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def test_full_extraction():
    srv, b = base()
    try:
        out = execute({"url": b, "extract": ["title", "headings", "links", "forms", "meta", "text"]},
                      FakeCtx())
        assert out["title"] == "Test Page"
        assert {"level": "h1", "text": "Hello"} in out["headings"]
        assert any(l["href"] == b + "about" for l in out["links"])
        assert out["meta"]["description"] == "a test page"
        form = out["forms"][0]
        assert form["name"] == "login" and form["action"] == b + "login"
        assert form["method"] == "POST"
        assert {f["name"] for f in form["fields"]} == {"user", "pw", "tok"}
        assert "Some visible text here." in out["text_excerpt"]
    finally:
        srv.shutdown()


def test_default_extract_subset():
    srv, b = base()
    try:
        out = execute({"url": b}, FakeCtx())
        assert set(out) == {"url", "title", "headings", "links"}
    finally:
        srv.shutdown()


def test_non_html_rejected():
    srv, b = base()
    try:
        try:
            execute({"url": b + "binary"}, FakeCtx())
            assert False, "should raise"
        except ModuleError as e:
            assert "not an html" in str(e).lower()
    finally:
        srv.shutdown()


def test_invalid_inputs():
    c = FakeCtx()
    for bad in [{}, {"url": ""}, {"url": "notaurl"},
                {"url": "http://x", "extract": []},
                {"url": "http://x", "extract": ["nonsense"]},
                {"url": "http://x", "max_bytes": 0}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_unreachable_is_module_error():
    try:
        execute({"url": "http://127.0.0.1:1/", "timeout_seconds": 1}, FakeCtx())
        assert False, "should raise"
    except ModuleError:
        pass


def test_forms_extracted_but_not_submitted():
    # extraction is read-only: no approval path exists in this module
    srv, b = base()
    try:
        c = FakeCtx()
        execute({"url": b, "extract": ["forms"]}, c)
        assert c.approvals == []
    finally:
        srv.shutdown()
