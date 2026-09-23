"""Tests for oauth_connect. Token endpoint is a local fixture — no live network."""
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied

GOT = []


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
        GOT.append(urllib.parse.parse_qs(self.rfile.read(n).decode()))
        if self.path == "/badjson":
            body = b"not json"
        elif self.path == "/notoken":
            body = json.dumps({"error": "x"}).encode()
        else:
            body = json.dumps({"access_token": "AT-123", "token_type": "Bearer",
                               "expires_in": 3600, "refresh_token": "RT-456"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
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
    GOT.clear()
    srv = make_server()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def ctx(**kw):
    args = {"approve": True, "auth": {"acme_secret": "shhh"}}
    args.update(kw)
    return FakeCtx(**args)


BASE_INPUTS = {"provider": "acme", "client_id": "cid",
               "redirect_uri": "https://app.example/cb"}


def test_build_auth_url():
    d = dict(BASE_INPUTS)
    d.update(action="build_auth_url",
             authorization_endpoint="https://auth.example/authorize",
             scope=["read", "write"], state="xyz-state")
    out = execute(d, ctx())
    assert out["provider"] == "acme"
    assert out["state"] == "xyz-state"
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(out["auth_url"]).query)
    assert q["response_type"] == ["code"]
    assert q["client_id"] == ["cid"]
    assert q["redirect_uri"] == ["https://app.example/cb"]
    assert q["scope"] == ["read write"]
    assert q["state"] == ["xyz-state"]


def test_build_auth_url_generates_state():
    d = dict(BASE_INPUTS)
    d.update(action="build_auth_url", authorization_endpoint="https://auth.example/authorize")
    out = execute(d, ctx())
    assert len(out["state"]) >= 16


def test_build_auth_url_needs_no_approval():
    d = dict(BASE_INPUTS)
    d.update(action="build_auth_url", authorization_endpoint="https://auth.example/authorize")
    c = ctx()
    execute(d, c)
    assert c.approvals == []


def test_exchange_code_happy_path():
    srv, b = base()
    try:
        d = dict(BASE_INPUTS)
        d.update(action="exchange_code", token_endpoint=b + "/token",
                 code="authcode-1", secret_provider="acme_secret")
        c = ctx()
        out = execute(d, c)
        assert out["access_token"] == "AT-123"
        assert out["token_type"] == "Bearer"
        assert out["expires_in"] == 3600
        assert out["refresh_token_issued"] is True
        assert "refresh_token" not in out  # value withheld in v1 outputs
        assert len(c.approvals) == 1
        assert GOT[0]["grant_type"] == ["authorization_code"]
        assert GOT[0]["client_secret"] == ["shhh"]
        assert "AT-123" not in json.dumps(c.logs)  # tokens never logged
    finally:
        srv.shutdown()


def test_exchange_missing_secret_raises_auth_missing():
    srv, b = base()
    try:
        d = dict(BASE_INPUTS)
        d.update(action="exchange_code", token_endpoint=b + "/token",
                 code="c", secret_provider="nosuch")
        try:
            execute(d, ctx(auth={}))
            assert False, "should raise"
        except AuthMissing:
            pass
    finally:
        srv.shutdown()


def test_exchange_denied_sends_nothing():
    srv, b = base()
    try:
        d = dict(BASE_INPUTS)
        d.update(action="exchange_code", token_endpoint=b + "/token",
                 code="c", secret_provider="acme_secret")
        try:
            execute(d, ctx(approve=False))
            assert False, "should raise"
        except ApprovalDenied:
            pass
        assert GOT == []
    finally:
        srv.shutdown()


def test_exchange_bad_json_is_module_error():
    srv, b = base()
    try:
        d = dict(BASE_INPUTS)
        d.update(action="exchange_code", token_endpoint=b + "/badjson",
                 code="c", secret_provider="acme_secret")
        try:
            execute(d, ctx())
            assert False, "should raise"
        except ModuleError as e:
            assert "non-JSON" in str(e)
    finally:
        srv.shutdown()


def test_exchange_missing_access_token_is_module_error():
    srv, b = base()
    try:
        d = dict(BASE_INPUTS)
        d.update(action="exchange_code", token_endpoint=b + "/notoken",
                 code="c", secret_provider="acme_secret")
        try:
            execute(d, ctx())
            assert False, "should raise"
        except ModuleError as e:
            assert "access_token" in str(e)
    finally:
        srv.shutdown()


def test_invalid_inputs():
    c = ctx()
    for bad in [{}, {"action": "build_auth_url"},
                {"action": "build_auth_url", "provider": "p", "client_id": "c",
                 "redirect_uri": "ftp://x"},  # bad endpoint caught too
                {"action": "exchange_code", "provider": "p", "client_id": "c",
                 "redirect_uri": "https://x/cb"}]:  # missing token_endpoint/code/secret
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass
