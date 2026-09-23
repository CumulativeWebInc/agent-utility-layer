"""End-to-end tests for spine/exec_api.py (stdlib + pytest).

Spins up the real HTTP server on an ephemeral port and drives it with urllib.
"""

import json
import threading
import urllib.request
import urllib.error

import pytest

from auth import KeyStore
from billing import total_for
from registry import repo_root
from exec_api import make_server


@pytest.fixture()
def server(tmp_path, monkeypatch):
    keys = tmp_path / "keys.json"
    ledger = tmp_path / "ledger.jsonl"
    approvals = tmp_path / "approvals.jsonl"
    monkeypatch.setenv("AUL_KEYS_FILE", str(keys))
    monkeypatch.setenv("AUL_LEDGER_FILE", str(ledger))
    monkeypatch.setenv("AUL_APPROVALS_FILE", str(approvals))
    store = KeyStore()
    full_key = store.issue("full", ["*"])
    scoped_key = store.issue("scoped", ["template:demo"])
    wrong_key = store.issue("wrong", ["other:thing"])
    srv = make_server(0, allow_demo=True, root=repo_root())
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield {"base": base, "full": full_key, "scoped": scoped_key, "wrong": wrong_key,
           "ledger": str(ledger), "approvals": str(approvals)}
    srv.shutdown()
    srv.server_close()


def _get(base, path, key=None):
    req = urllib.request.Request(base + path)
    if key:
        req.add_header("X-Agent-Key", key)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(base, payload):
    req = urllib.request.Request(
        base + "/v1/execute",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health_and_capabilities(server):
    status, body = _get(server["base"], "/v1/health")
    assert status == 200 and body["ok"] is True
    status, body = _get(server["base"], "/v1/capabilities")
    names = [c["name"] for c in body["capabilities"]]
    assert "template_demo" in names


def test_execute_demo_happy_path(server):
    status, body = _post(server["base"], {
        "capability": "template_demo",
        "inputs": {"message": "hello"},
        "agent_key": server["scoped"],
        "demo": True,
    })
    assert status == 200, body
    assert body["demo"] is True
    assert body["result"]["echo"] == "hello"
    assert body["result"]["simulated"] is True
    assert body["billing"]["amount_usd"] == pytest.approx(0.001)
    billed = total_for(_principal_id(server), path=server["ledger"])
    assert billed == pytest.approx(0.001)


def _principal_id(server):
    from auth import key_fingerprint
    return key_fingerprint(server["scoped"])


def test_execute_bills_ledger(server):
    before = total_for(_principal_id(server), path=server["ledger"])
    _post(server["base"], {"capability": "template_demo",
                           "inputs": {"message": "x"},
                           "agent_key": server["scoped"], "demo": True})
    after = total_for(_principal_id(server), path=server["ledger"])
    assert after - before == pytest.approx(0.001)


def test_execute_bad_key_401(server):
    status, body = _post(server["base"], {"capability": "template_demo",
                                         "inputs": {"message": "x"},
                                         "agent_key": "aul_bogus", "demo": True})
    assert status == 401


def test_execute_permission_denied_403(server):
    status, body = _post(server["base"], {"capability": "template_demo",
                                         "inputs": {"message": "x"},
                                         "agent_key": server["wrong"], "demo": True})
    assert status == 403
    assert body["error"]["code"] == "permission_denied"


def test_execute_invalid_inputs_422(server):
    status, body = _post(server["base"], {"capability": "template_demo",
                                         "inputs": {},
                                         "agent_key": server["scoped"], "demo": True})
    assert status == 422


def test_execute_unknown_capability_404(server):
    status, _ = _post(server["base"], {"capability": "nope",
                                      "inputs": {},
                                      "agent_key": server["scoped"], "demo": True})
    assert status == 404


def test_execute_real_mode_missing_credential_409(server, monkeypatch):
    monkeypatch.delenv("AUL_CRED_TEMPLATE_PROVIDER", raising=False)
    status, body = _post(server["base"], {"capability": "template_demo",
                                         "inputs": {"message": "x"},
                                         "agent_key": server["scoped"]})
    assert status == 409
    assert body["error"]["code"] == "auth_missing"


def test_execute_real_mode_with_credential_200(server, monkeypatch):
    monkeypatch.setenv("AUL_CRED_TEMPLATE_PROVIDER", "test-secret")
    status, body = _post(server["base"], {"capability": "template_demo",
                                         "inputs": {"message": "x"},
                                         "agent_key": server["scoped"]})
    assert status == 200, body
    assert body["demo"] is False


def test_execute_real_destructive_needs_approval(server, monkeypatch):
    monkeypatch.setenv("AUL_CRED_TEMPLATE_PROVIDER", "test-secret")
    monkeypatch.delenv("AUL_AUTO_APPROVE", raising=False)
    status, body = _post(server["base"], {"capability": "template_demo",
                                         "inputs": {"message": "x", "destructive": True},
                                         "agent_key": server["scoped"]})
    assert status == 403
    assert body["error"]["code"] == "approval_denied"
    assert len(open(server["approvals"]).read().strip().split("\n")) >= 1
