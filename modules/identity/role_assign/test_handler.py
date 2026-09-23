"""Tests for role_assign. Memory-backed — no network."""
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


def test_assign_and_list():
    c = FakeCtx()
    out = execute({"action": "assign", "principal": "svc1", "role": "operator"}, c)
    assert out["ok"] is True and out["roles"] == ["operator"]
    assert len(c.approvals) == 1
    listed = execute({"action": "list", "principal": "svc1"}, c)
    assert listed["roles"] == ["operator"]


def test_assign_idempotent():
    c = FakeCtx()
    execute({"action": "assign", "principal": "svc1", "role": "viewer"}, c)
    out = execute({"action": "assign", "principal": "svc1", "role": "viewer"}, c)
    assert out["roles"] == ["viewer"]


def test_revoke():
    c = FakeCtx()
    execute({"action": "assign", "principal": "svc1", "role": "operator"}, c)
    execute({"action": "assign", "principal": "svc1", "role": "viewer"}, c)
    out = execute({"action": "revoke", "principal": "svc1", "role": "operator"}, c)
    assert out["roles"] == ["viewer"]


def test_unknown_role_rejected():
    try:
        execute({"action": "assign", "principal": "svc1", "role": "superuser"}, FakeCtx())
        assert False, "should raise"
    except ModuleError as e:
        assert "unknown role" in str(e)


def test_admin_assignment_flagged_in_approval():
    c = FakeCtx()
    execute({"action": "assign", "principal": "svc1", "role": "admin"}, c)
    assert "PRIVILEGED" in c.approvals[0]


def test_denied_assign_writes_nothing():
    c = FakeCtx(approve=False)
    try:
        execute({"action": "assign", "principal": "svc1", "role": "operator"}, c)
        assert False, "should raise"
    except ApprovalDenied:
        pass
    assert c.memory_get("rbac:assignments") in (None, {})


def test_denied_revoke_writes_nothing():
    c = FakeCtx()
    execute({"action": "assign", "principal": "svc1", "role": "operator"}, c)
    c._approve = False
    try:
        execute({"action": "revoke", "principal": "svc1", "role": "operator"}, c)
        assert False, "should raise"
    except ApprovalDenied:
        pass
    assert execute({"action": "list", "principal": "svc1"}, c)["roles"] == ["operator"]


def test_list_all():
    c = FakeCtx()
    execute({"action": "assign", "principal": "a", "role": "viewer"}, c)
    n_before = len(c.approvals)
    out = execute({"action": "list"}, c)
    assert out["roles"] == {"a": ["viewer"]}
    assert len(c.approvals) == n_before  # list itself needs no approval


def test_invalid_inputs():
    c = FakeCtx()
    for bad in [{}, {"action": "assign"}, {"action": "assign", "principal": "a"},
                {"action": "assign", "principal": "", "role": "viewer"},
                {"action": "frobnicate"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass
