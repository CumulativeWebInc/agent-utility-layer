"""Tests for permission_check. Memory-seeded RBAC — no network."""
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


def seeded():
    c = FakeCtx()
    c.memory_set("rbac:assignments", {
        "ops1": ["operator"],
        "root": ["admin"],
        "ro": ["viewer"],
    })
    return c


def test_operator_allowed_http_request():
    out = execute({"principal": "ops1", "action": "request", "resource": "http:request"},
                  seeded())
    assert out["allowed"] is True and out["rule"] is not None


def test_operator_denied_vault_write():
    out = execute({"principal": "ops1", "action": "write", "resource": "vault:write"},
                  seeded())
    assert out["allowed"] is False and out["rule"] is None


def test_admin_wildcard_allows_everything():
    out = execute({"principal": "root", "action": "nuke", "resource": "anything:at_all"},
                  seeded())
    assert out["allowed"] is True


def test_viewer_read_only():
    c = seeded()
    assert execute({"principal": "ro", "action": "request", "resource": "http:request"}, c)["allowed"] is True
    assert execute({"principal": "ro", "action": "send", "resource": "http:send"}, c)["allowed"] is False


def test_unknown_principal_default_deny():
    out = execute({"principal": "nobody", "action": "read", "resource": "http:request"},
                  seeded())
    assert out["allowed"] is False
    assert "default-deny" in out["reason"]


def test_custom_grants_override_defaults():
    c = seeded()
    c.memory_set("rbac:grants", {"custom": {"vault:*": ["write"]}})
    c.memory_set("rbac:assignments", {"svc": ["custom"]})
    assert execute({"principal": "svc", "action": "write", "resource": "vault:write"}, c)["allowed"] is True
    assert execute({"principal": "svc", "action": "read", "resource": "vault:read"}, c)["allowed"] is False


def test_invalid_inputs():
    c = seeded()
    for bad in [{}, {"principal": "a"}, {"principal": "a", "action": "x"},
                {"principal": "", "action": "x", "resource": "y"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_read_only_no_approval_no_mutation():
    c = seeded()
    before = dict(c._mem)
    execute({"principal": "ops1", "action": "request", "resource": "http:request"}, c)
    assert c.approvals == []
    assert c._mem["rbac:assignments"] == before["rbac:assignments"]
