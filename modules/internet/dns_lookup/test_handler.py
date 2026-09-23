"""Tests for dns_lookup. localhost only — no live network dependency."""
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


def test_a_record_localhost():
    out = execute({"hostname": "localhost"}, FakeCtx())
    assert out["record_type"] == "A"
    assert out["resolved"] is True
    assert "127.0.0.1" in out["answers"]


def test_aaaa_record_localhost():
    out = execute({"hostname": "localhost", "record_type": "AAAA"}, FakeCtx())
    assert out["resolved"] is True
    assert any(":" in a for a in out["answers"])  # ::1


def test_cname_returns_list():
    out = execute({"hostname": "localhost", "record_type": "CNAME"}, FakeCtx())
    assert isinstance(out["answers"], list)


def test_nonexistent_hostname_is_module_error():
    # Overlong label (>63 chars) always fails resolution, independent of the
    # sandbox's wildcard DNS — deterministic without live network.
    try:
        execute({"hostname": "x" * 64 + ".invalid"}, FakeCtx())
        assert False, "should raise"
    except ModuleError as e:
        assert "failed" in str(e)


def test_unsupported_record_type_rejected():
    for bad in ["MX", "TXT", "SRV"]:
        try:
            execute({"hostname": "localhost", "record_type": bad}, FakeCtx())
            assert False, f"should raise for {bad}"
        except ModuleError as e:
            assert "stdlib" in str(e)


def test_invalid_inputs():
    for bad in [{}, {"hostname": ""}, {"hostname": 123},
                {"hostname": "localhost", "timeout_seconds": 0},
                {"hostname": "localhost", "timeout_seconds": 99}]:
        try:
            execute(bad, FakeCtx())
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_output_schema_keys():
    out = execute({"hostname": "localhost"}, FakeCtx())
    assert set(out) == {"hostname", "record_type", "answers", "resolved"}


def test_no_approval_needed_and_billed():
    c = FakeCtx()
    execute({"hostname": "localhost"}, c)
    assert c.approvals == []
    assert c.bills and c.bills[0][0] == 0.001
