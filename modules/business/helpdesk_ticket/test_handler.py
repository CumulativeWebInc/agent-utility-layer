"""pytest for helpdesk_ticket."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def _create(ctx, **over):
    data = {"title": "Printer jam", "description": "3rd floor", "requester": "kim"}
    data.update(over)
    return handler.execute({"action": "create", "data": data}, ctx)["ticket"]


def test_create_and_get_happy_path():
    ctx = make_ctx()
    t = _create(ctx)
    assert t["status"] == "open"
    got = handler.execute({"action": "get", "ticket_id": t["id"]}, ctx)
    assert got["ticket"]["title"] == "Printer jam"
    assert set(got.keys()) == {"status", "ticket", "tickets", "count"}


def test_full_lifecycle_comment_assign_close_reopen():
    ctx = make_ctx()
    t = _create(ctx)
    handler.execute({"action": "assign", "ticket_id": t["id"], "assignee": "ops-1"}, ctx)
    c = handler.execute({"action": "add_comment", "ticket_id": t["id"],
                         "comment": "investigating", "data": {"author": "ops-1"}}, ctx)
    assert len(c["ticket"]["comments"]) == 1
    closed = handler.execute({"action": "close", "ticket_id": t["id"]}, ctx)
    assert closed["ticket"]["status"] == "closed"
    assert closed["ticket"]["resolved_at"] is not None
    reopened = handler.execute({"action": "reopen", "ticket_id": t["id"]}, ctx)
    assert reopened["ticket"]["status"] == "open"


def test_invalid_priority_rejected():
    ctx = make_ctx()
    try:
        _create(ctx, priority="cosmic")
    except handler.ModuleError as e:
        assert "priority" in str(e)
    else:
        raise AssertionError("expected ModuleError for bad priority")


def test_update_unknown_field_and_bad_status_rejected():
    ctx = make_ctx()
    t = _create(ctx)
    for bad in ({"hacked": True}, {"status": "teleported"}):
        try:
            handler.execute({"action": "update", "ticket_id": t["id"], "data": bad}, ctx)
        except handler.ModuleError:
            pass
        else:
            raise AssertionError("expected ModuleError for %r" % (bad,))


def test_reopen_only_from_resolved_or_closed():
    ctx = make_ctx()
    t = _create(ctx)
    try:
        handler.execute({"action": "reopen", "ticket_id": t["id"]}, ctx)
    except handler.ModuleError as e:
        assert "reopened" in str(e)
    else:
        raise AssertionError("expected ModuleError reopening an open ticket")


def test_get_unknown_ticket_never_fabricates():
    ctx = make_ctx()
    try:
        handler.execute({"action": "get", "ticket_id": "tkt_nope"}, ctx)
    except handler.ModuleError as e:
        assert "no ticket" in str(e)
    else:
        raise AssertionError("expected ModuleError")


def test_list_filters_by_status():
    ctx = make_ctx()
    a = _create(ctx)
    _create(ctx, title="Second")
    handler.execute({"action": "close", "ticket_id": a["id"]}, ctx)
    open_t = handler.execute({"action": "list", "status": "open"}, ctx)
    assert open_t["count"] == 1
    closed_t = handler.execute({"action": "list", "status": "closed"}, ctx)
    assert closed_t["count"] == 1


def test_billing_recorded():
    ctx = make_ctx()
    _create(ctx)
    assert ctx.bills and ctx.bills[0]["amount_usd"] == 0.001
