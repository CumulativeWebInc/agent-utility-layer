"""Tests for user_auth. Pure memory-backed — no network."""
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


PW = "correct-horse-battery-staple"


def test_register_then_verify():
    c = FakeCtx()
    out = execute({"action": "register", "username": "ada", "credential": PW}, c)
    assert out["ok"] is True and out["username"] == "ada"
    assert len(c.approvals) == 1  # register needs approval
    out2 = execute({"action": "verify", "username": "ada", "credential": PW}, c)
    assert out2["ok"] is True


def test_wrong_password_rejected():
    c = FakeCtx()
    execute({"action": "register", "username": "ada", "credential": PW}, c)
    try:
        execute({"action": "verify", "username": "ada", "credential": "wrong-password-xyz"}, c)
        assert False, "should raise"
    except ModuleError as e:
        assert "invalid credential" in str(e)


def test_unknown_user_rejected():
    try:
        execute({"action": "verify", "username": "ghost", "credential": PW}, FakeCtx())
        assert False, "should raise"
    except ModuleError as e:
        assert "unknown username" in str(e)


def test_weak_password_rejected():
    try:
        execute({"action": "register", "username": "ada", "credential": "short"}, FakeCtx())
        assert False, "should raise"
    except ModuleError as e:
        assert "at least 12" in str(e)


def test_duplicate_register_rejected():
    c = FakeCtx()
    execute({"action": "register", "username": "ada", "credential": PW}, c)
    try:
        execute({"action": "register", "username": "ada", "credential": PW}, c)
        assert False, "should raise"
    except ModuleError as e:
        assert "already registered" in str(e)


def test_register_denied_no_record_created():
    c = FakeCtx(approve=False)
    try:
        execute({"action": "register", "username": "ada", "credential": PW}, c)
        assert False, "should raise"
    except ApprovalDenied:
        pass
    try:
        execute({"action": "verify", "username": "ada", "credential": PW}, c)
        assert False, "user should not exist"
    except ModuleError:
        pass


def test_rotate_changes_credential():
    c = FakeCtx()
    execute({"action": "register", "username": "ada", "credential": PW}, c)
    new = "new-longer-password-here"
    out = execute({"action": "rotate", "username": "ada", "credential": PW,
                   "new_credential": new}, c)
    assert out["ok"] is True
    assert execute({"action": "verify", "username": "ada", "credential": new}, c)["ok"] is True
    try:
        execute({"action": "verify", "username": "ada", "credential": PW}, c)
        assert False, "old password must stop working"
    except ModuleError:
        pass


def test_plaintext_never_stored():
    c = FakeCtx()
    execute({"action": "register", "username": "ada", "credential": PW}, c)
    blob = json.dumps(c._mem)
    assert PW not in blob
    assert "hash" in blob and "salt" in blob


def test_invalid_inputs():
    for bad in [{}, {"action": "verify"}, {"action": "verify", "username": "u"},
                {"action": "nope", "username": "u", "credential": PW},
                {"action": "verify", "username": "u", "credential": ""}]:
        try:
            execute(bad, FakeCtx())
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass
