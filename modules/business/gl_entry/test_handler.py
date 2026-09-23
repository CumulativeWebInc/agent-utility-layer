"""pytest for gl_entry — double-entry enforcement verified."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def _post(ctx, lines, **kw):
    payload = {"action": "post", "date": "2026-09-23", "memo": kw.pop("memo", "test"),
               "lines": lines}
    payload.update(kw)
    return handler.execute(payload, ctx)["entry"]


def test_post_balanced_entry_happy_path():
    ctx = make_ctx()
    e = _post(ctx, [
        {"account": "Cash", "debit": 1000},
        {"account": "Revenue", "credit": 1000},
    ])
    assert e["total"] == "1000"
    got = handler.execute({"action": "get", "entry_id": e["id"]}, ctx)
    assert set(got.keys()) == {"status", "entry", "entries", "balances", "count"}
    assert got["entry"]["id"] == e["id"]


def test_unbalanced_entry_rejected():
    ctx = make_ctx()
    try:
        _post(ctx, [
            {"account": "Cash", "debit": 1000},
            {"account": "Revenue", "credit": 999.99},
        ])
    except handler.ModuleError as e:
        assert "does not balance" in str(e)
    else:
        raise AssertionError("expected ModuleError for unbalanced entry")
    # ledger must be empty — rejected entries never land
    assert handler.execute({"action": "list"}, ctx)["count"] == 0


def test_line_with_both_sides_or_neither_rejected():
    ctx = make_ctx()
    for bad in ([{"account": "A", "debit": 5, "credit": 5}, {"account": "B", "credit": 10}],
                [{"account": "A", "debit": 0, "credit": 0}, {"account": "B", "credit": 10}]):
        try:
            _post(ctx, bad)
        except handler.ModuleError:
            pass
        else:
            raise AssertionError("expected ModuleError for %r" % (bad,))


def test_negative_amount_rejected():
    ctx = make_ctx()
    try:
        _post(ctx, [{"account": "Cash", "debit": -50}, {"account": "Revenue", "credit": 50}])
    except handler.ModuleError as e:
        assert ">= 0" in str(e)
    else:
        raise AssertionError("expected ModuleError for negative amount")


def test_trial_balance_math():
    ctx = make_ctx()
    _post(ctx, [{"account": "Cash", "debit": 1000}, {"account": "Revenue", "credit": 1000}])
    _post(ctx, [{"account": "Rent Expense", "debit": 200}, {"account": "Cash", "credit": 200}])
    res = handler.execute({"action": "trial_balance"}, ctx)
    by_acct = {r["account"]: r for r in res["balances"]}
    assert by_acct["Cash"]["balance"] == "800"
    assert by_acct["Revenue"]["balance"] == "-1000"
    assert by_acct["Rent Expense"]["balance"] == "200"


def test_void_excludes_from_trial_balance_but_keeps_audit_trail():
    ctx = make_ctx()
    e = _post(ctx, [{"account": "Cash", "debit": 500}, {"account": "Revenue", "credit": 500}])
    v = handler.execute({"action": "void", "entry_id": e["id"]}, ctx)
    assert v["entry"]["voided"] is True
    res = handler.execute({"action": "trial_balance"}, ctx)
    assert res["count"] == 0
    # entry still retrievable — audit trail kept
    got = handler.execute({"action": "get", "entry_id": e["id"]}, ctx)
    assert got["entry"]["voided"] is True
    try:
        handler.execute({"action": "void", "entry_id": e["id"]}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError double-voiding")


def test_get_unknown_entry_never_fabricates():
    ctx = make_ctx()
    try:
        handler.execute({"action": "get", "entry_id": "je_nope"}, ctx)
    except handler.ModuleError as e:
        assert "no journal entry" in str(e)
    else:
        raise AssertionError("expected ModuleError")


def test_bad_date_format_rejected():
    ctx = make_ctx()
    try:
        _post(ctx, [{"account": "Cash", "debit": 1}, {"account": "Revenue", "credit": 1}],
              date="09/23/2026")
    except handler.ModuleError as e:
        assert "YYYY-MM-DD" in str(e)
    else:
        raise AssertionError("expected ModuleError for bad date")
