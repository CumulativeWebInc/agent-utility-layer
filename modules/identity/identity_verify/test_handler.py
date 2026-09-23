"""Tests for identity_verify. Memory-backed workflow — no network."""
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


def new_case(c, subject="Jane Doe"):
    return execute({"action": "start", "subject": subject}, c)["case_id"]


def test_full_approve_workflow():
    c = FakeCtx()
    cid = new_case(c)
    execute({"action": "submit_evidence", "case_id": cid,
             "evidence_type": "government_id", "evidence_ref": "vault://ids/doc-1"}, c)
    execute({"action": "submit_evidence", "case_id": cid,
             "evidence_type": "selfie", "evidence_ref": "vault://ids/selfie-1"}, c)
    out = execute({"action": "decision", "case_id": cid, "decision": "approve",
                   "notes": "ID matched"}, c)
    assert out["status"] == "approved"
    assert len(out["evidence"]) == 2
    assert out["decided_at"] is not None
    assert len(c.approvals) == 1  # only decision needs approval


def test_reject_workflow():
    c = FakeCtx()
    cid = new_case(c)
    out = execute({"action": "decision", "case_id": cid, "decision": "reject",
                   "notes": "blurry"}, c)
    assert out["status"] == "rejected"


def test_decision_denied_keeps_pending():
    c = FakeCtx(approve=False)
    cid = new_case(c)
    try:
        execute({"action": "decision", "case_id": cid, "decision": "approve"}, c)
        assert False, "should raise"
    except ApprovalDenied:
        pass
    assert execute({"action": "status", "case_id": cid}, c)["status"] == "pending"


def test_terminal_cases_reject_further_actions():
    c = FakeCtx()
    cid = new_case(c)
    execute({"action": "decision", "case_id": cid, "decision": "approve"}, c)
    for extra in [
        {"action": "submit_evidence", "case_id": cid, "evidence_type": "x", "evidence_ref": "y"},
        {"action": "decision", "case_id": cid, "decision": "reject"},
    ]:
        try:
            execute(extra, c)
            assert False, "should raise"
        except ModuleError as e:
            assert "approved" in str(e) or "terminal" in str(e) or "only pending" in str(e)


def test_double_decision_rejected():
    c = FakeCtx()
    cid = new_case(c)
    execute({"action": "decision", "case_id": cid, "decision": "approve"}, c)
    try:
        execute({"action": "decision", "case_id": cid, "decision": "approve"}, c)
        assert False, "should raise"
    except ModuleError:
        pass


def test_unknown_case_rejected():
    try:
        execute({"action": "status", "case_id": "case_nope"}, FakeCtx())
        assert False, "should raise"
    except ModuleError as e:
        assert "not found" in str(e)


def test_start_requires_subject():
    try:
        execute({"action": "start"}, FakeCtx())
        assert False, "should raise"
    except ModuleError as e:
        assert "subject" in str(e)


def test_invalid_inputs():
    c = FakeCtx()
    cid = new_case(c)
    for bad in [{}, {"action": "nope"},
                {"action": "submit_evidence", "case_id": cid},
                {"action": "decision", "case_id": cid, "decision": "maybe"},
                {"action": "status"}]:
        try:
            execute(bad, c)
            assert False, f"should raise for {bad}"
        except ModuleError:
            pass


def test_status_returns_case_view():
    c = FakeCtx()
    cid = new_case(c, subject="John Smith")
    out = execute({"action": "status", "case_id": cid}, c)
    assert out["case_id"] == cid and out["subject"] == "John Smith"
    assert out["status"] == "pending" and out["evidence"] == []
