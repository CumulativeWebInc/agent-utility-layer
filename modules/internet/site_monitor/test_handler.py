"""Tests for site_monitor. Local fixture server — no live network."""
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied

MODE = {"code": 200, "text": "service healthy"}


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
        body = MODE["text"].encode()
        self.send_response(MODE["code"])
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


def inp(url, **kw):
    d = {"url": url}
    d.update(kw)
    return d


def test_first_check_up_no_state_change():
    srv, b = base()
    try:
        MODE.update(code=200, text="service healthy")
        out = execute(inp(b), FakeCtx())
        assert out["ok"] is True and out["state"] == "up"
        assert out["previous_state"] is None and out["state_changed"] is False
        assert out["response_ms"] >= 0 and out["checked_at"]
    finally:
        srv.shutdown()


def test_state_change_detected_up_to_down():
    srv, b = base()
    try:
        c = FakeCtx()
        MODE.update(code=200, text="ok")
        execute(inp(b, monitor_id="m1"), c)
        MODE.update(code=500, text="boom")
        out = execute(inp(b, monitor_id="m1"), c)
        assert out["state"] == "down" and out["ok"] is False
        assert out["previous_state"] == "up" and out["state_changed"] is True
        out2 = execute(inp(b, monitor_id="m1"), c)
        assert out2["state_changed"] is False  # stable now
    finally:
        srv.shutdown()


def test_expected_text_mismatch_marks_down():
    srv, b = base()
    try:
        MODE.update(code=200, text="service healthy")
        out = execute(inp(b, expected_text="something else entirely"), FakeCtx())
        assert out["ok"] is False and out["state"] == "down"
    finally:
        srv.shutdown()


def test_expected_status_mismatch():
    srv, b = base()
    try:
        MODE.update(code=200, text="ok")
        out = execute(inp(b, expected_status=201), FakeCtx())
        assert out["ok"] is False
    finally:
        srv.shutdown()


def test_unreachable_is_down_not_exception():
    out = execute(inp("http://127.0.0.1:1/", timeout_seconds=1, monitor_id="m2"), FakeCtx())
    assert out["ok"] is False and out["state"] == "down" and out["status"] is None


def test_invalid_inputs():
    c = FakeCtx()
    for bad in [{}, {"url": ""}, {"url": "ftp://x"},
                {"url": "http://x", "expected_status": "200"},
                {"url": "http://x", "timeout_seconds": 0},
                {"url": "http://x", "monitor_id": 5}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_no_approval_required():
    srv, b = base()
    try:
        MODE.update(code=200, text="ok")
        c = FakeCtx()
        execute(inp(b), c)
        assert c.approvals == []
    finally:
        srv.shutdown()
