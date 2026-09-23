"""pytest for esign_request — approval gate and honest pending state."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def _payload(**over):
    p = {"action": "create", "document_name": "Freelance Work Order",
         "document_ref": "draft_contract:wo-001",
         "signers": [{"name": "Jane Doe", "email": "jane@example.com"},
                     {"name": "Client Co", "email": "ops@client.co"}],
         "expires_in_days": 7}
    p.update(over)
    return p


def test_create_requires_approval_and_stays_pending():
    ctx = make_ctx()
    res = handler.execute(_payload(), ctx)
    assert res["status"] == "created"
    assert res["approval_id"].startswith("appr_test_")
    req = res["request"]
    assert req["status"] == "pending_signature"
    assert all(s["status"] == "pending_signature" and s["signed_at"] is None
               for s in req["signers"])
    assert set(res.keys()) == {"status", "request", "requests", "approval_id", "count"}
    # approval push billed at $0.01 plus the $0.001 execution
    amounts = sorted(b["amount_usd"] for b in ctx.bills)
    assert amounts == [0.001, 0.01]


def test_approval_denied_blocks_creation():
    ctx = make_ctx(approve="deny")
    try:
        handler.execute(_payload(), ctx)
    except handler.ApprovalDenied:
        pass
    else:
        raise AssertionError("expected ApprovalDenied")
    # nothing landed when the human said no
    assert handler.execute({"action": "list"}, ctx)["count"] == 0


def test_invalid_signer_email_rejected_before_approval():
    ctx = make_ctx()
    try:
        handler.execute(_payload(signers=[{"name": "X", "email": "nope"}]), ctx)
    except handler.ModuleError as e:
        assert "email" in str(e)
    else:
        raise AssertionError("expected ModuleError for bad email")
    assert ctx.approvals_requested == []  # validation happens before any approval


def test_duplicate_signer_email_rejected():
    ctx = make_ctx()
    try:
        handler.execute(_payload(signers=[
            {"name": "A", "email": "dup@example.com"},
            {"name": "B", "email": "DUP@example.com"}]), ctx)
    except handler.ModuleError as e:
        assert "duplicate" in str(e)
    else:
        raise AssertionError("expected ModuleError for duplicate email")


def test_cancel_and_double_cancel():
    ctx = make_ctx()
    rid = handler.execute(_payload(), ctx)["request"]["id"]
    c = handler.execute({"action": "cancel", "request_id": rid}, ctx)
    assert c["request"]["status"] == "cancelled"
    try:
        handler.execute({"action": "cancel", "request_id": rid}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError double-cancel")


def test_get_unknown_request_never_fabricates():
    ctx = make_ctx()
    try:
        handler.execute({"action": "get", "request_id": "esr_nope"}, ctx)
    except handler.ModuleError as e:
        assert "no signature request" in str(e)
    else:
        raise AssertionError("expected ModuleError")


def test_expiry_window_bounds():
    ctx = make_ctx()
    for bad in (0, 91, "soon"):
        try:
            handler.execute(_payload(expires_in_days=bad), ctx)
        except handler.ModuleError:
            pass
        else:
            raise AssertionError("expected ModuleError for expires_in_days=%r" % (bad,))


def test_list_returns_created_requests():
    ctx = make_ctx()
    handler.execute(_payload(), ctx)
    handler.execute(_payload(document_name="NDA"), ctx)
    res = handler.execute({"action": "list"}, ctx)
    assert res["count"] == 2
    assert all(r["status"] == "pending_signature" for r in res["requests"])
