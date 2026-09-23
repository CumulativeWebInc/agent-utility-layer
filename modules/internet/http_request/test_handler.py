"""Tests for http_request. Local http.server fixture — no live network."""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied


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
    def _send(self, code, body=b"hello"):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
        elif self.path == "/missing":
            self._send(404, b"nope")
        else:
            self._send(200, b'{"ok": true}')

    def do_HEAD(self):
        self._send(200, b"")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.wfile and self.rfile.read(n)
        self._send(201, b"created")

    def log_message(self, *a):
        pass


def make_server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def base():
    srv = make_server()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_get_happy_path():
    srv, b = base()
    try:
        out = execute({"url": b + "/ok"}, FakeCtx())
        assert out["status"] == 200
        assert json.loads(out["body"]) == {"ok": True}
        assert out["bytes_total"] > 0 and not out["truncated"]
        assert out["final_url"] == b + "/ok"
        assert out["elapsed_ms"] >= 0
    finally:
        srv.shutdown()


def test_post_requires_approval_and_sends():
    srv, b = base()
    try:
        ctx = FakeCtx()
        out = execute({"method": "POST", "url": b + "/post", "body": "x=1"}, ctx)
        assert out["status"] == 201
        assert len(ctx.approvals) == 1 and "POST" in ctx.approvals[0]
        assert ctx.bills and ctx.bills[0][0] == 0.001
    finally:
        srv.shutdown()


def test_post_denied_raises_and_sends_nothing():
    srv, b = base()
    try:
        ctx = FakeCtx(approve=False)
        try:
            execute({"method": "DELETE", "url": b + "/x"}, ctx)
            assert False, "should raise"
        except ApprovalDenied:
            pass
        assert ctx.logs == []  # denied before any network
    finally:
        srv.shutdown()


def test_invalid_inputs():
    ctx = FakeCtx()
    for bad in [{}, {"url": ""}, {"url": "ftp://x"}, {"url": "not a url"},
                {"url": "http://x", "method": "BREW"},
                {"url": "http://x", "timeout_seconds": 0},
                {"url": "http://x", "timeout_seconds": 61},
                {"url": "http://x", "max_response_bytes": -1},
                {"url": "http://x", "body": 123}]:
        try:
            execute(bad, ctx)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_http_error_status_returned_not_raised():
    srv, b = base()
    try:
        out = execute({"url": b + "/missing"}, FakeCtx())
        assert out["status"] == 404
        assert out["body"] == "nope"
    finally:
        srv.shutdown()


def test_redirect_followed():
    srv, b = base()
    try:
        out = execute({"url": b + "/redir"}, FakeCtx())
        assert out["status"] == 200
        assert out["final_url"] == b + "/ok"
    finally:
        srv.shutdown()


def test_head_method():
    srv, b = base()
    try:
        out = execute({"method": "HEAD", "url": b + "/ok"}, FakeCtx())
        assert out["status"] == 200
        assert out["body"] == ""
    finally:
        srv.shutdown()


def test_unreachable_host_module_error():
    ctx = FakeCtx()
    try:
        execute({"url": "http://127.0.0.1:1/", "timeout_seconds": 1}, ctx)
        assert False, "should raise"
    except ModuleError as e:
        assert "failed" in str(e)
