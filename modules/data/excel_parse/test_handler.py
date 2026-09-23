"""Tests for excel_parse handler. Minimal .xlsx fixtures are built inline."""

import base64
import io
import os
import sys
import zipfile

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


def make_xlsx(sheets_spec):
    """sheets_spec: list of (name, rows) where rows are lists of cell values.
    str values use shared strings; ('inline', s) uses inlineStr; numbers raw."""
    buf = io.BytesIO()
    shared = []
    shared_idx = {}
    sheet_xmls = []
    for i, (name, rows) in enumerate(sheets_spec):
        cells_xml = []
        for r, row in enumerate(rows, start=1):
            tds = []
            for c, val in enumerate(row):
                ref = f"{chr(65 + c)}{r}"
                if isinstance(val, tuple) and val[0] == "inline":
                    tds.append(
                        f'<c r="{ref}" t="inlineStr"><is><t>{val[1]}</t></is></c>'
                    )
                elif isinstance(val, str):
                    if val not in shared_idx:
                        shared_idx[val] = len(shared)
                        shared.append(val)
                    tds.append(f'<c r="{ref}" t="s"><v>{shared_idx[val]}</v></c>')
                elif isinstance(val, bool):
                    tds.append(f'<c r="{ref}" t="b"><v>{1 if val else 0}</v></c>')
                else:
                    tds.append(f'<c r="{ref}"><v>{val}</v></c>')
            cells_xml.append(f"<row r=\"{r}\">{''.join(tds)}</row>")
        sheet_xmls.append(
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(cells_xml)}</sheetData></worksheet>"
        )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        sheets_el = "".join(
            f'<sheet name="{n}" sheetId="{i + 1}"/>' for i, (n, _) in enumerate(sheets_spec)
        )
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheets>{sheets_el}</sheets></workbook>",
        )
        si_el = "".join(
            f'<si><t>{s}</t></si>' for s in shared
        )
        z.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{si_el}</sst>",
        )
        for i, sx in enumerate(sheet_xmls):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", sx)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_happy_path_shared_strings_and_numbers():
    b64 = make_xlsx([("Data", [["name", "age"], ["Ann", 30], ["Bo", 41.5]])])
    out = execute({"file_base64": b64}, FakeCtx())
    assert out["status"] == "ok"
    assert out["active_sheet"] == "Data"
    assert out["columns"] == ["name", "age"]
    assert out["rows"][0] == {"name": "Ann", "age": 30}
    assert out["rows"][1] == {"name": "Bo", "age": 41.5}
    assert out["row_count"] == 2


def test_inline_str_and_boolean():
    b64 = make_xlsx([("S", [["a", "b"], [("inline", "hi"), True]])])
    out = execute({"file_base64": b64}, FakeCtx())
    assert out["rows"][0] == {"a": "hi", "b": True}


def test_multi_sheet_selection():
    b64 = make_xlsx([("One", [["x"], [1]]), ("Two", [["y"], [2]])])
    out = execute({"file_base64": b64}, FakeCtx())
    assert [s["name"] for s in out["sheets"]] == ["One", "Two"]
    assert out["active_sheet"] == "One"
    out2 = execute({"file_base64": b64, "sheet": "Two"}, FakeCtx())
    assert out2["active_sheet"] == "Two"
    assert out2["rows"][0] == {"y": 2}


def test_missing_sheet_name_rejected():
    b64 = make_xlsx([("Only", [["x"], [1]])])
    try:
        execute({"file_base64": b64, "sheet": "Nope"}, FakeCtx())
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "not found" in str(e).lower()


def test_legacy_xls_rejected():
    ole = base64.b64encode(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64).decode()
    try:
        execute({"file_base64": ole}, FakeCtx())
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert ".xls" in str(e)


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    good = make_xlsx([("S", [["a"], [1]])])
    cases = [
        {"file_base64": "!!!"},
        {"file_base64": base64.b64encode(b"not a zip").decode()},
        {"file_base64": ""},
        {},
        {"file_base64": good, "sheet": 5},
        {"file_base64": good, "header_row": "yes"},
        {"file_base64": good, "max_rows": -1},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:40]!r}")
        except ModuleError:
            pass


def test_no_header_generates_columns():
    b64 = make_xlsx([("S", [[1, 2], [3, 4]])])
    out = execute({"file_base64": b64, "header_row": False}, FakeCtx())
    assert out["columns"] == ["col_1", "col_2"]
    assert out["row_count"] == 2


def test_outputs_match_schema_keys():
    b64 = make_xlsx([("S", [["a"], [1]])])
    out = execute({"file_base64": b64}, FakeCtx())
    assert set(out.keys()) == {
        "status", "sheets", "active_sheet", "columns", "rows",
        "row_count", "truncated", "warnings",
    }
