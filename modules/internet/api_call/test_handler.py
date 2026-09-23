"""Tests for api_call. Local fixture server asserts the Bearer header — no live network."""
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
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        auth = self.headers.get("Authorization")
        if auth != "Bearer sekrit-token":
            self._json(401, {"error": "unauthorized"})
            return
        if self.path == "/text":
            body = b"plain text response"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(200, {"path": self.path, "authed": True})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        self._json(200, {"echo": json.loads(raw.decode())})

    def log_message(self, *a):
        pass


def make_server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def base():
    srv = make_server()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def ctx(auth=None, approve=True):
    return FakeCtx(approve=approve, auth=auth or {"myapi": "sekrit-token"})


def test_get_with_bearer_auth():
    srv, b = base()
    try:
        out = execute({"auth_provider": "myapi", "base_url": b,
                       "endpoint": "/things", "query": {"a": "1"}}, ctx())
        assert out["status"] == 200
        assert out["data"]["authed"] is True
        assert out["data"]["path"].startswith("/things")
    finally:
        srv.shutdown()


def test_wrong_credential_gets_401_not_fake_success():
    srv, b = base()
    try:
        out = execute({"auth_provider": "myapi", "base_url": b, "endpoint": "/x"},
                      ctx(auth={"myapi": "wrong"}))
        assert out["status"] == 401  # real provider rejection surfaces
    finally:
        srv.shutdown()


def test_missing_credential_raises_auth_missing():
    srv, b = base()
    try:
        try:
            execute({"auth_provider": "nosuch", "base_url": b, "endpoint": "/x"}, ctx(auth={}))
            assert False, "should raise"
        except AuthMissing:
            pass
    finally:
        srv.shutdown()


def test_post_json_body_with_approval():
    srv, b = base()
    try:
        c = ctx()
        out = execute({"auth_provider": "myapi", "base_url": b, "endpoint": "/create",
                       "method": "POST", "json_body": {"name": "widget"}}, c)
        assert out["status"] == 200
        assert out["data"]["echo"] == {"name": "widget"}
        assert len(c.approvals) == 1
    finally:
        srv.shutdown()


def test_post_denied_raises_approval_denied():
    srv, b = base()
    try:
        try:
            execute({"auth_provider": "myapi", "base_url": b, "endpoint": "/create",
                     "method": "POST", "json_body": {}}, ctx(approve=False))
            assert False, "should raise"
        except ApprovalDenied:
            pass
    finally:
        srv.shutdown()


def test_non_json_response_returned_as_text():
    srv, b = base()
    try:
        out = execute({"auth_provider": "myapi", "base_url": b, "endpoint": "/text"}, ctx())
        assert out["status"] == 200
        assert out["data"] == "plain text response"
    finally:
        srv.shutdown()


def test_invalid_inputs():
    c = ctx()
    for bad in [{}, {"auth_provider": "x"}, {"auth_provider": "x", "base_url": b"/x"},
                {"auth_provider": "myapi", "base_url": "http://x"},  # missing endpoint
                {"auth_provider": "myapi", "base_url": "http://x", "endpoint": "/e",
                 "method": "BREW"},
                {"auth_provider": "myapi", "base_url": "http://x", "endpoint": "/e",
                 "query": "nope"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except (ModuleError, AuthMissing):
            pass


def test_credential_never_logged():
    srv, b = base()
    try:
        c = ctx()
        execute({"auth_provider": "myapi", "base_url": b, "endpoint": "/x"}, c)
        blob = json.dumps(c.logs)
        assert "sekrit-token" not in blob
    finally:
        srv.shutdown()
