"""pytest for crm_record — FakeCtx exercises the real handler logic."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def test_create_and_get_happy_path():
    ctx = make_ctx()
    created = handler.execute(
        {"action": "create", "record_type": "contact",
         "data": {"name": "Ada Lovelace", "email": "ada@example.com"}},
        ctx,
    )
    assert created["status"] == "created"
    rid = created["record"]["id"]
    got = handler.execute({"action": "get", "record_id": rid}, ctx)
    assert got["record"]["name"] == "Ada Lovelace"
    assert got["record"]["record_type"] == "contact"
    assert set(got.keys()) == {"status", "record", "records", "count"}


def test_update_and_list_filter():
    ctx = make_ctx()
    a = handler.execute({"action": "create", "record_type": "deal",
                         "data": {"name": "Deal A"}}, ctx)["record"]["id"]
    handler.execute({"action": "create", "record_type": "contact",
                     "data": {"name": "Bob"}}, ctx)
    updated = handler.execute(
        {"action": "update", "record_id": a, "data": {"amount": 5000}}, ctx)
    assert updated["status"] == "updated"
    assert updated["record"]["amount"] == 5000
    listed = handler.execute({"action": "list", "record_type": "deal"}, ctx)
    assert listed["count"] == 1
    assert listed["records"][0]["id"] == a


def test_search_matches_across_fields():
    ctx = make_ctx()
    handler.execute({"action": "create", "record_type": "company",
                     "data": {"name": "Cumulative Web Inc", "email": "hp@cumulativeweb.com"}}, ctx)
    handler.execute({"action": "create", "record_type": "contact",
                     "data": {"name": "Zoe", "email": "zoe@other.com"}}, ctx)
    res = handler.execute({"action": "search", "query": "cumulative"}, ctx)
    assert res["count"] == 1
    assert res["records"][0]["name"] == "Cumulative Web Inc"


def test_invalid_action_raises():
    ctx = make_ctx()
    try:
        handler.execute({"action": "teleport"}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError for invalid action")


def test_create_requires_record_type_and_data():
    ctx = make_ctx()
    for bad in (
        {"action": "create", "data": {"name": "x"}},
        {"action": "create", "record_type": "alien", "data": {"name": "x"}},
        {"action": "create", "record_type": "contact"},
    ):
        try:
            handler.execute(bad, ctx)
        except handler.ModuleError:
            pass
        else:
            raise AssertionError("expected ModuleError for %r" % (bad,))


def test_get_missing_id_raises_never_fabricates():
    ctx = make_ctx()
    try:
        handler.execute({"action": "get", "record_id": "rec_doesnotexist"}, ctx)
    except handler.ModuleError as e:
        assert "no CRM record" in str(e)
    else:
        raise AssertionError("expected ModuleError for unknown id")


def test_delete_then_get_fails():
    ctx = make_ctx()
    rid = handler.execute(
        {"action": "create", "record_type": "lead", "data": {"name": "L"}}, ctx
    )["record"]["id"]
    assert handler.execute({"action": "delete", "record_id": rid}, ctx)["status"] == "deleted"
    try:
        handler.execute({"action": "get", "record_id": rid}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError after delete")


def test_limit_bounds_checked():
    ctx = make_ctx()
    try:
        handler.execute({"action": "list", "limit": 0}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError for limit=0")
    try:
        handler.execute({"action": "list", "limit": 501}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError for limit=501")
