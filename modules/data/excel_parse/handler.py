"""excel_parse — real .xlsx parsing with stdlib zipfile + xml.etree.

Honest limits (also in README):
- Supports .xlsx (OOXML) only: shared strings, inline strings, numbers,
  booleans, dates as raw serials (not converted to dates).
- Does NOT support: legacy .xls (BIFF binary — rejected with ModuleError),
  formula evaluation (cached values only), charts, macros, images, pivot
  tables, merged-cell semantics beyond raw cell values.
"""

import base64
import binascii
import io
import re
import zipfile
import xml.etree.ElementTree as ET


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _col_to_index(col: str) -> int:
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _cell_text(cell, shared):
    t = cell.get("t", "n")
    v_el = cell.find("v")
    if t == "s":  # shared string
        try:
            return shared[int(v_el.text)]
        except (IndexError, ValueError, TypeError, AttributeError):
            return ""
    if t == "inlineStr":
        is_el = cell.find("is")
        if is_el is None:
            return ""
        return "".join(node.text or "" for node in is_el.iter("t"))
    if t == "str":  # cached formula string
        return v_el.text if v_el is not None else ""
    if t == "b":  # boolean
        return v_el.text == "1" if v_el is not None else False
    if t == "e":  # error
        return f"#ERR:{v_el.text}" if v_el is not None else "#ERR"
    if v_el is None or v_el.text is None:
        return ""
    raw = v_el.text.strip()
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_sheet(zf, path, shared):
    try:
        root = _strip_ns(ET.fromstring(zf.read(path)))
    except (KeyError, ET.ParseError) as e:
        raise ModuleError(f"cannot read worksheet '{path}': {e}")
    rows = []
    for row_el in root.iter("row"):
        cells = {}
        max_idx = -1
        for cell in row_el.iter("c"):
            ref = cell.get("r", "")
            m = _CELL_REF_RE.match(ref)
            if not m:
                continue
            idx = _col_to_index(m.group(1))
            max_idx = max(max_idx, idx)
            cells[idx] = _cell_text(cell, shared)
        if max_idx >= 0:
            rows.append([cells.get(i, "") for i in range(max_idx + 1)])
    return rows


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    b64 = inputs.get("file_base64")
    if not isinstance(b64, str) or not b64.strip():
        raise ModuleError("input 'file_base64' must be a non-empty base64 string")
    try:
        raw = base64.b64decode(b64.strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ModuleError(f"input 'file_base64' is not valid base64: {e}")
    if raw[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ModuleError(
            "legacy .xls (BIFF binary) is not supported — convert to .xlsx first"
        )
    if not raw.startswith(b"PK"):
        raise ModuleError("input is not an .xlsx file (missing ZIP signature)")

    sheet_wanted = inputs.get("sheet")
    header_row = inputs.get("header_row", True)
    if not isinstance(header_row, bool):
        raise ModuleError("input 'header_row' must be a boolean")
    max_rows = inputs.get("max_rows", 10000)
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows <= 0:
        raise ModuleError("input 'max_rows' must be a positive integer")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as e:
        raise ModuleError(f"input is not a readable ZIP/.xlsx: {e}")

    try:
        wb_root = _strip_ns(ET.fromstring(zf.read("xl/workbook.xml")))
    except (KeyError, ET.ParseError) as e:
        raise ModuleError(f"workbook.xml missing or unreadable: {e}")
    sheets = []
    for i, sh in enumerate(wb_root.iter("sheet")):
        name = sh.get("name", f"Sheet{i + 1}")
        sheets.append({"name": name, "path": f"xl/worksheets/sheet{i + 1}.xml"})
    if not sheets:
        raise ModuleError("workbook contains no sheets")

    shared = []
    try:
        ss_root = _strip_ns(ET.fromstring(zf.read("xl/sharedStrings.xml")))
        for si in ss_root.iter("si"):
            shared.append("".join(node.text or "" for node in si.iter("t")))
    except KeyError:
        pass  # workbook with no shared strings
    except ET.ParseError as e:
        raise ModuleError(f"sharedStrings.xml unreadable: {e}")

    warnings = []
    target = sheets[0]
    if sheet_wanted is not None:
        if not isinstance(sheet_wanted, str):
            raise ModuleError("input 'sheet' must be a sheet name string")
        matches = [s for s in sheets if s["name"] == sheet_wanted]
        if not matches:
            raise ModuleError(
                f"sheet '{sheet_wanted}' not found. available: "
                + ", ".join(s["name"] for s in sheets)
            )
        target = matches[0]

    parsed = {}
    for s in sheets:
        parsed[s["name"]] = _parse_sheet(zf, s["path"], shared)
    sheet_rows = parsed[target["name"]]
    sheet_info = [
        {"name": s["name"], "row_count": len(parsed[s["name"]])} for s in sheets
    ]

    if header_row and sheet_rows:
        columns = [str(c) for c in sheet_rows[0]]
        data = sheet_rows[1:]
    elif sheet_rows:
        width = max(len(r) for r in sheet_rows)
        columns = [f"col_{i + 1}" for i in range(width)]
        data = sheet_rows
    else:
        columns, data = [], []

    truncated = len(data) > max_rows
    data = data[:max_rows]
    rows = []
    for r in data:
        padded = list(r) + [""] * (len(columns) - len(r))
        rows.append({columns[i]: padded[i] for i in range(len(columns))})
    if any(
        isinstance(v, str) and v.startswith("#ERR") for r in rows for v in r.values()
    ):
        warnings.append("some cells contained formula errors (reported as #ERR:code)")

    ctx.log("excel_parse", {"sheets": len(sheets), "active": target["name"],
                            "rows": len(rows)})
    return {
        "status": "ok",
        "sheets": sheet_info,
        "active_sheet": target["name"],
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "warnings": warnings,
    }
