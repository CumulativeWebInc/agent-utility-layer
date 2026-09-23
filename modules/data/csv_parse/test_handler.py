"""Tests for csv_parse handler."""

import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handler import ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self):
        self.logs = []

    def auth_get(self, provider):
        raise AssertionError("no provider needed")

    def approval_request(self, summary, timeout_seconds=300):
        raise AssertionError("no approval needed")

    def memory_get(self, key):
        return None

    def memory_set(self, key, value):
        pass

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        pass


def test_happy_path():
    out = execute({"csv_text": "a,b,c\n1,2,3\n4,5,6"}, FakeCtx())
    assert out["status"] == "ok"
    assert out["columns"] == ["a", "b", "c"]
    assert out["rows"] == [{"a": "1", "b": "2", "c": "3"},
                           {"a": "4", "b": "5", "c": "6"}]
    assert out["row_count"] == 2
    assert out["delimiter"] == ","
    assert out["truncated"] is False


def test_quoted_fields_with_commas_and_newlines():
    txt = 'name,note\n"Doe, Jane","line1\nline2"\nBob,hi'
    out = execute({"csv_text": txt}, FakeCtx())
    assert out["rows"][0] == {"name": "Doe, Jane", "note": "line1\nline2"}
    assert out["row_count"] == 2


def test_delimiter_autodetect_and_explicit():
    semi = "a;b\n1;2"
    out = execute({"csv_text": semi}, FakeCtx())
    assert out["delimiter"] == ";"
    assert out["rows"][0] == {"a": "1", "b": "2"}
    out2 = execute({"csv_text": "a|b\n1|2", "delimiter": "|"}, FakeCtx())
    assert out2["delimiter"] == "|"


def test_base64_input_and_bom():
    raw = "\ufeffa,b\n1,2".encode("utf-8")
    b64 = base64.b64encode(raw).decode()
    out = execute({"csv_base64": b64}, FakeCtx())
    assert out["columns"] == ["a", "b"]  # BOM stripped
    assert out["row_count"] == 1


def test_no_header_generates_columns():
    out = execute({"csv_text": "1,2\n3,4,5", "has_header": False}, FakeCtx())
    assert out["columns"] == ["col_1", "col_2", "col_3"]
    assert out["rows"][0]["col_3"] == ""  # short row padded


def test_row_cap_truncates():
    txt = "a\n" + "\n".join(str(i) for i in range(10))
    out = execute({"csv_text": txt, "max_rows": 3}, FakeCtx())
    assert out["truncated"] is True
    assert out["row_count"] == 3


def test_skip_empty_rows():
    out = execute({"csv_text": "a,b\n1,2\n\n   \n3,4"}, FakeCtx())
    assert out["row_count"] == 2


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    cases = [
        {},
        {"csv_text": "a", "csv_base64": "eA=="},  # both given
        {"csv_text": "   "},
        {"csv_base64": "!!!"},
        {"csv_text": "a\n1", "delimiter": ";;"},
        {"csv_text": "a\n1", "has_header": "yes"},
        {"csv_text": "a\n1", "max_rows": 0},
        {"csv_text": "\n\n"},  # no data rows
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:40]!r}")
        except ModuleError:
            pass


def test_outputs_match_schema_keys():
    out = execute({"csv_text": "a\n1"}, FakeCtx())
    assert set(out.keys()) == {
        "status", "columns", "rows", "row_count", "delimiter",
        "truncated", "char_count",
    }
