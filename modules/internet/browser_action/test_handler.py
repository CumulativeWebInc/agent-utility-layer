"""Tests for browser_action. Local fixture server — no live network."""
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied

PAGE = b"""<html><body>
<form name="signup" action="/signup" method="post">
<input type="text" name="email"><input type="hidden" name="src" value="web">
<input type="submit" value="Go"></form>
<form action="/other" method="get"><input name="q"></form>
</body></html>"""

POSTED = []


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
        if self.path == "/page":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)
        elif self.path == "/noforms":
            body = b"<html><body>no forms</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        POSTED.append(urllib.parse.parse_qs(self.rfile.read(n).decode()))
        body = b"thanks"
        self.send_response(200)
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
    POSTED.clear()
    srv = make_server()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_submit_form_happy_path():
    srv, b = base()
    try:
        c = FakeCtx()
        out = execute({"action": "submit_form", "url": b + "/page",
                       "form": {"name": "signup"},
                       "fields": {"email": "a@b.c"}}, c)
        assert out["status"] == 200
        assert out["submitted_to"] == b + "/signup"
        assert len(c.approvals) == 1
        assert POSTED[0]["email"] == ["a@b.c"]
        assert POSTED[0]["src"] == ["web"]  # hidden default carried
        assert "email" in out["fields_sent"] and "src" in out["fields_sent"]
    finally:
        srv.shutdown()


def test_submit_by_index():
    srv, b = base()
    try:
        out = execute({"action": "submit_form", "url": b + "/page",
                       "form": {"index": 0}, "fields": {"email": "x@y.z"}}, FakeCtx())
        assert out["status"] == 200
    finally:
        srv.shutdown()


def test_denied_submits_nothing():
    srv, b = base()
    try:
        try:
            execute({"action": "submit_form", "url": b + "/page",
                     "fields": {"email": "a@b.c"}}, FakeCtx(approve=False))
            assert False, "should raise"
        except ApprovalDenied:
            pass
        assert POSTED == []
    finally:
        srv.shutdown()


def test_unknown_field_rejected():
    srv, b = base()
    try:
        try:
            execute({"action": "submit_form", "url": b + "/page",
                     "fields": {"nosuchfield": "1"}}, FakeCtx())
            assert False, "should raise"
        except ModuleError as e:
            assert "unknown form fields" in str(e)
    finally:
        srv.shutdown()


def test_no_forms_rejected():
    srv, b = base()
    try:
        try:
            execute({"action": "submit_form", "url": b + "/noforms",
                     "fields": {"a": "b"}}, FakeCtx())
            assert False, "should raise"
        except ModuleError as e:
            assert "no HTML forms" in str(e)
    finally:
        srv.shutdown()


def test_invalid_inputs():
    c = FakeCtx()
    for bad in [{}, {"action": "click"}, {"action": "submit_form"},
                {"action": "submit_form", "url": "http://x"},  # missing fields
                {"action": "submit_form", "url": "ftp://x", "fields": {}},
                {"action": "submit_form", "url": "http://x", "fields": "nope"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_bad_form_index_rejected():
    srv, b = base()
    try:
        try:
            execute({"action": "submit_form", "url": b + "/page",
                     "form": {"index": 9}, "fields": {"email": "a"}}, FakeCtx())
            assert False, "should raise"
        except ModuleError as e:
            assert "out of range" in str(e)
    finally:
        srv.shutdown()
