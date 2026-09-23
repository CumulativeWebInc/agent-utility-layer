"""Tests for apikey_vault. Pure memory-backed crypto — no network."""
import json
import sys

from .handler import execute, ModuleError, AuthMissing, ApprovalDenied, encrypt, decrypt


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


def ctx(**kw):
    args = {"approve": True, "auth": {"vault_master": "master-passphrase"}}
    args.update(kw)
    return FakeCtx(**args)


def test_store_then_retrieve_roundtrip():
    c = ctx()
    out = execute({"action": "store", "key_name": "stripe", "key_value": "sk_live_ABC123",
                   "provider": "stripe"}, c)
    assert out["ok"] is True and out["version"] == 1
    assert out["last4"] == "C123"
    got = execute({"action": "retrieve", "key_name": "stripe"}, c)
    assert got["value"] == "sk_live_ABC123"
    assert got["provider"] == "stripe"


def test_plaintext_never_in_memory_or_logs():
    c = ctx()
    execute({"action": "store", "key_name": "k", "key_value": "TOPSECRETVALUE"}, c)
    assert "TOPSECRETVALUE" not in json.dumps(c._mem)
    assert "TOPSECRETVALUE" not in json.dumps(c.logs)


def test_wrong_master_key_fails_decrypt():
    c = ctx()
    execute({"action": "store", "key_name": "k", "key_value": "v1-v1-v1-v1"}, c)
    c2 = ctx(auth={"vault_master": "wrong-passphrase"})
    c2._mem = c._mem  # same persisted store, wrong master
    try:
        execute({"action": "retrieve", "key_name": "k"}, c2)
        assert False, "should raise"
    except ModuleError as e:
        assert "decryption failed" in str(e)


def test_missing_master_key_raises_auth_missing():
    try:
        execute({"action": "store", "key_name": "k", "key_value": "v"}, ctx(auth={}))
        assert False, "should raise"
    except AuthMissing:
        pass


def test_rotate_bumps_version():
    c = ctx()
    execute({"action": "store", "key_name": "k", "key_value": "old-value-1"}, c)
    out = execute({"action": "rotate", "key_name": "k", "key_value": "new-value-2"}, c)
    assert out["version"] == 2
    assert execute({"action": "retrieve", "key_name": "k"}, c)["value"] == "new-value-2"


def test_revoke_removes_key():
    c = ctx()
    execute({"action": "store", "key_name": "k", "key_value": "v-v-v-v-v"}, c)
    assert execute({"action": "revoke", "key_name": "k"}, c)["ok"] is True
    try:
        execute({"action": "retrieve", "key_name": "k"}, c)
        assert False, "should raise"
    except ModuleError as e:
        assert "not found" in str(e)


def test_list_shows_names_not_values():
    c = ctx()
    execute({"action": "store", "key_name": "k", "key_value": "SECRETVALUE1"}, c)
    out = execute({"action": "list"}, c)
    assert out["keys"][0]["key_name"] == "k"
    assert "SECRETVALUE1" not in json.dumps(out)


def test_writes_require_approval_denied_blocks():
    c = ctx(approve=False)
    try:
        execute({"action": "store", "key_name": "k", "key_value": "v"}, c)
        assert False, "should raise"
    except ApprovalDenied:
        pass
    assert c.memory_get("apikey_vault:keys") in (None, {})


def test_tampered_blob_detected():
    m = b"master-passphrase"
    blob = encrypt(m, b"data")
    blob["ct"] = blob["ct"][:-2] + ("AA" if not blob["ct"].endswith("AA") else "BB")
    try:
        decrypt(m, blob)
        assert False, "should raise"
    except ModuleError as e:
        assert "tampered" in str(e)


def test_invalid_inputs():
    c = ctx()
    for bad in [{}, {"action": "store"}, {"action": "retrieve"},
                {"action": "store", "key_name": "k"},
                {"action": "bogus"},
                {"action": "store", "key_name": "k", "key_value": ""}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass
