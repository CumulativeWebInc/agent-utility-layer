"""Tests for webhook_emit. Local fixture server verifies signature — no live network."""
import hashlib
import hmac
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied

RECEIVED = []


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
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        RECEIVED.append({"sig": self.headers.get("X-Webhook-Signature"), "body": body})
        if self.path == "/fail":
            self.send_response(500)
        else:
            self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def make_server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def base():
    RECEIVED.clear()
    srv = make_server()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def ctx(**kw):
    args = {"approve": True, "auth": {"hooksecret": "s3cr3t"}}
    args.update(kw)
    return FakeCtx(**args)


def test_signed_emit_happy_path():
    srv, b = base()
    try:
        out = execute({"url": b + "/hook", "event_name": "order.paid",
                       "payload": {"id": 7}, "secret_provider": "hooksecret"}, ctx())
        assert out["status"] == 200 and out["delivered"] is True
        assert out["signature"] and out["signature"].startswith("sha256=")
        assert len(RECEIVED) == 1
        body = RECEIVED[0]["body"]
        expect = "sha256=" + hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()
        assert RECEIVED[0]["sig"] == expect
        assert json.loads(body) == {"event": "order.paid", "payload": {"id": 7}}
    finally:
        srv.shutdown()


def test_unsigned_emit_when_sign_false():
    srv, b = base()
    try:
        out = execute({"url": b + "/hook", "event_name": "ping",
                       "payload": {}, "sign": False}, ctx())
        assert out["delivered"] is True
        assert out["signature"] is None
        assert RECEIVED[0]["sig"] is None
    finally:
        srv.shutdown()


def test_approval_always_required():
    srv, b = base()
    try:
        c = ctx()
        execute({"url": b + "/hook", "event_name": "e", "payload": {},
                 "sign": False}, c)
        assert len(c.approvals) == 1
    finally:
        srv.shutdown()


def test_denied_sends_nothing():
    srv, b = base()
    try:
        try:
            execute({"url": b + "/hook", "event_name": "e", "payload": {},
                     "sign": False}, ctx(approve=False))
            assert False, "should raise"
        except ApprovalDenied:
            pass
        assert RECEIVED == []
    finally:
        srv.shutdown()


def test_missing_signing_secret_raises_auth_missing():
    srv, b = base()
    try:
        try:
            execute({"url": b + "/hook", "event_name": "e", "payload": {},
                     "secret_provider": "nosuch"}, ctx(auth={}))
            assert False, "should raise"
        except AuthMissing:
            pass
    finally:
        srv.shutdown()


def test_sign_true_without_provider_is_module_error():
    try:
        execute({"url": "http://127.0.0.1:9/", "event_name": "e", "payload": {}}, ctx())
        assert False, "should raise"
    except ModuleError:
        pass


def test_server_error_marks_undelivered():
    srv, b = base()
    try:
        out = execute({"url": b + "/fail", "event_name": "e", "payload": {},
                       "sign": False}, ctx())
        assert out["status"] == 500 and out["delivered"] is False
    finally:
        srv.shutdown()


def test_invalid_inputs():
    c = ctx()
    for bad in [{}, {"url": "http://x"}, {"url": "http://x", "event_name": "e"},
                {"url": "ftp://x", "event_name": "e", "payload": {}},
                {"url": "http://x", "event_name": "e", "payload": "nope"},
                {"url": "http://x", "event_name": "e", "payload": {}, "sign": "yes"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass
