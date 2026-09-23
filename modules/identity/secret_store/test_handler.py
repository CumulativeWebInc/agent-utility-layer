"""Tests for secret_store. Pure memory-backed crypto — no network."""
import json
import sys

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


def ctx(**kw):
    args = {"approve": True, "auth": {"vault_master": "master-passphrase"}}
    args.update(kw)
    return FakeCtx(**args)


def test_store_retrieve_versions():
    c = ctx()
    assert execute({"action": "store", "name": "db", "value": "pw-one-1111"}, c)["version"] == 1
    assert execute({"action": "store", "name": "db", "value": "pw-two-2222"}, c)["version"] == 2
    assert execute({"action": "retrieve", "name": "db"}, c)["value"] == "pw-two-2222"
    assert execute({"action": "retrieve", "name": "db", "version": 1}, c)["value"] == "pw-one-1111"


def test_versions_lists_history():
    c = ctx()
    execute({"action": "store", "name": "db", "value": "pw-one-1111"}, c)
    execute({"action": "store", "name": "db", "value": "pw-two-2222"}, c)
    out = execute({"action": "versions", "name": "db"}, c)
    assert [v["version"] for v in out["versions"]] == [1, 2]
    assert out["versions"][1]["current"] is True
    assert "pw-two-2222" not in json.dumps(out)  # versions never leak values


def test_rollback_points_current_at_old_version():
    c = ctx()
    execute({"action": "store", "name": "db", "value": "pw-one-1111"}, c)
    execute({"action": "store", "name": "db", "value": "pw-two-2222"}, c)
    out = execute({"action": "rollback", "name": "db", "version": 1}, c)
    assert out["ok"] is True and out["version"] == 1
    assert execute({"action": "retrieve", "name": "db"}, c)["value"] == "pw-one-1111"
    # history intact
    assert len(execute({"action": "versions", "name": "db"}, c)["versions"]) == 2


def test_rollback_bad_version_rejected():
    c = ctx()
    execute({"action": "store", "name": "db", "value": "pw-one-1111"}, c)
    try:
        execute({"action": "rollback", "name": "db", "version": 99}, c)
        assert False, "should raise"
    except ModuleError as e:
        assert "not found" in str(e)


def test_rollback_denied_keeps_current():
    c = ctx(approve=False)
    # store is also a write; use approving ctx for setup then deny for rollback
    c2 = ctx()
    c2._mem = c._mem
    execute({"action": "store", "name": "db", "value": "pw-one-1111"}, c2)
    execute({"action": "store", "name": "db", "value": "pw-two-2222"}, c2)
    c._mem = c2._mem
    try:
        execute({"action": "rollback", "name": "db", "version": 1}, c)
        assert False, "should raise"
    except ApprovalDenied:
        pass
    assert execute({"action": "retrieve", "name": "db"}, c)["value"] == "pw-two-2222"


def test_list_names_not_values():
    c = ctx()
    execute({"action": "store", "name": "db", "value": "SECRET-ABC-1"}, c)
    out = execute({"action": "list"}, c)
    assert out["names"][0]["name"] == "db"
    assert "SECRET-ABC-1" not in json.dumps(out)


def test_missing_master_key_raises_auth_missing():
    try:
        execute({"action": "list"}, ctx(auth={}))
        assert False, "should raise"
    except AuthMissing:
        pass


def test_unknown_secret_rejected():
    try:
        execute({"action": "retrieve", "name": "ghost"}, ctx())
        assert False, "should raise"
    except ModuleError as e:
        assert "not found" in str(e)


def test_plaintext_never_persisted():
    c = ctx()
    execute({"action": "store", "name": "db", "value": "ULTRASECRET99"}, c)
    assert "ULTRASECRET99" not in json.dumps(c._mem)


def test_invalid_inputs():
    c = ctx()
    for bad in [{}, {"action": "store"}, {"action": "store", "name": "n"},
                {"action": "retrieve"}, {"action": "rollback", "name": "n"},
                {"action": "rollback", "name": "n", "version": "1"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass
