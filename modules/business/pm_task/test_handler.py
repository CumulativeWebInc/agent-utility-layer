"""pytest for pm_task."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def _create(ctx, **over):
    data = {"title": "Ship landing page", "project": "utility-layer", "priority": "high"}
    data.update(over)
    return handler.execute({"action": "create", "data": data}, ctx)["task"]


def test_create_get_output_schema():
    ctx = make_ctx()
    t = _create(ctx)
    assert t["status"] == "todo" and t["project"] == "utility-layer"
    got = handler.execute({"action": "get", "task_id": t["id"]}, ctx)
    assert set(got.keys()) == {"status", "task", "tasks", "count"}
    assert got["task"]["title"] == "Ship landing page"


def test_complete_and_reopen():
    ctx = make_ctx()
    t = _create(ctx)
    done = handler.execute({"action": "complete", "task_id": t["id"]}, ctx)
    assert done["status"] == "completed"
    assert done["task"]["completed_at"] is not None
    try:
        handler.execute({"action": "complete", "task_id": t["id"]}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError completing twice")
    reopened = handler.execute({"action": "reopen", "task_id": t["id"]}, ctx)
    assert reopened["task"]["status"] == "todo"


def test_assign_and_subtask():
    ctx = make_ctx()
    t = _create(ctx)
    a = handler.execute({"action": "assign", "task_id": t["id"], "assignee": "crew-f"}, ctx)
    assert a["task"]["assignee"] == "crew-f"
    s = handler.execute({"action": "add_subtask", "task_id": t["id"],
                         "data": {"title": "write handler"}}, ctx)
    assert len(s["task"]["subtasks"]) == 1
    assert s["task"]["subtasks"][0]["done"] is False


def test_create_requires_title_and_valid_priority():
    ctx = make_ctx()
    for bad in ({"action": "create", "data": {}},
                {"action": "create", "data": {"title": "x", "priority": "later"}}):
        try:
            handler.execute(bad, ctx)
        except handler.ModuleError:
            pass
        else:
            raise AssertionError("expected ModuleError for %r" % (bad,))


def test_update_rejects_unknown_field():
    ctx = make_ctx()
    t = _create(ctx)
    try:
        handler.execute({"action": "update", "task_id": t["id"],
                         "data": {"owner_ssn": "000-00-0000"}}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError for unknown field")


def test_get_unknown_id_never_fabricates():
    ctx = make_ctx()
    try:
        handler.execute({"action": "get", "task_id": "task_nope"}, ctx)
    except handler.ModuleError as e:
        assert "no task" in str(e)
    else:
        raise AssertionError("expected ModuleError")


def test_list_filters_project_and_status():
    ctx = make_ctx()
    a = _create(ctx, project="alpha")
    _create(ctx, project="beta")
    handler.execute({"action": "complete", "task_id": a["id"]}, ctx)
    res = handler.execute({"action": "list", "project": "alpha", "status": "done"}, ctx)
    assert res["count"] == 1
    assert res["tasks"][0]["id"] == a["id"]
