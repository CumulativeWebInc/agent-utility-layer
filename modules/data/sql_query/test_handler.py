"""Tests for sql_query handler. Databases are created locally in tmp."""

import base64
import os
import sqlite3
import sys
import tempfile

from .handler import ApprovalDenied, ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self, approve=True):
        self._approve = approve
        self.logs = []
        self.approvals = []

    def auth_get(self, provider):
        raise AssertionError("no provider needed")

    def approval_request(self, summary, timeout_seconds=300):
        self.approvals.append(summary)
        if not self._approve:
            raise ApprovalDenied("human said no")
        return "appr_fake_1"

    def memory_get(self, key):
        return None

    def memory_set(self, key, value):
        pass

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        pass


def make_db_b64():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, n REAL)")
    conn.executemany("INSERT INTO t VALUES (?, ?, ?)",
                     [(1, "a", 1.5), (2, "b", 2.5), (3, "c", 3.5)])
    conn.commit()
    conn.close()
    with open(path, "rb") as f:
        data = f.read()
    os.unlink(path)
    return base64.b64encode(data).decode("ascii")


def test_happy_path_select():
    out = execute({"db_base64": make_db_b64(),
                   "query": "SELECT id, name FROM t WHERE n > ? ORDER BY id",
                   "params": [2.0]}, FakeCtx())
    assert out["status"] == "ok"
    assert out["columns"] == ["id", "name"]
    assert out["rows"] == [{"id": 2, "name": "b"}, {"id": 3, "name": "c"}]
    assert out["row_count"] == 2
    assert out["read_only"] is True


def test_row_cap_truncates():
    out = execute({"db_base64": make_db_b64(), "query": "SELECT * FROM t",
                   "max_rows": 2}, FakeCtx())
    assert out["truncated"] is True
    assert out["row_count"] == 2


def test_write_blocked_in_read_only_mode():
    try:
        execute({"db_base64": make_db_b64(),
                 "query": "DROP TABLE t"}, FakeCtx())
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "read-only" in str(e).lower()


def test_write_with_approval_granted():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn0 = sqlite3.connect(path)
    conn0.execute("CREATE TABLE t (id INTEGER)")
    conn0.commit()
    conn0.close()
    try:
        out = execute({"db_path": path, "query": "INSERT INTO t VALUES (7)",
                       "read_only": False}, FakeCtx(approve=True))
        assert out["status"] == "ok"
        conn = sqlite3.connect(path)
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
        conn.close()
    finally:
        os.unlink(path)


def test_write_with_approval_denied():
    ctx = FakeCtx(approve=False)
    try:
        execute({"db_base64": make_db_b64(),
                 "query": "DELETE FROM t", "read_only": False}, ctx)
        raise AssertionError("expected ApprovalDenied")
    except ApprovalDenied:
        pass
    assert ctx.approvals  # approval was actually requested first


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    good = make_db_b64()
    cases = [
        {"query": "SELECT 1; SELECT 2", "db_base64": good},  # multi-statement
        {"query": "", "db_base64": good},
        {"query": "GRANT ALL", "db_base64": good},
        {"query": "SELECT * FROM missing", "db_base64": good},  # sqlite error
        {"query": "SELECT 1"},  # no db
        {"query": "SELECT 1", "db_base64": "!!!"},
        {"query": "SELECT 1",
         "db_base64": base64.b64encode(b"not sqlite").decode()},
        {"query": "SELECT 1", "db_base64": good, "db_path": "/x"},
        {"query": "SELECT 1", "db_path": "/does/not/exist.db"},
        {"query": "SELECT 1", "db_base64": good, "max_rows": 0},
        {"query": "SELECT ?", "db_base64": good, "params": "nope"},
        {"query": 42, "db_base64": good},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:50]!r}")
        except ModuleError:
            pass


def test_outputs_match_schema_keys():
    out = execute({"db_base64": make_db_b64(), "query": "SELECT 1 AS one"},
                  FakeCtx())
    assert set(out.keys()) == {
        "status", "columns", "rows", "row_count", "truncated", "read_only"
    }
    assert out["rows"] == [{"one": 1}]
