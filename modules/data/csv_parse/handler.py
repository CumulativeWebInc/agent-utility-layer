"""csv_parse — real CSV parsing via stdlib csv. Delimiter auto-detection."""

import base64
import binascii
import csv
import io


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _get_text(inputs) -> str:
    txt = inputs.get("csv_text")
    b64 = inputs.get("csv_base64")
    if txt is None and b64 is None:
        raise ModuleError("provide one of 'csv_text' or 'csv_base64'")
    if txt is not None and b64 is not None:
        raise ModuleError("provide only one of 'csv_text' or 'csv_base64'")
    if txt is not None:
        if not isinstance(txt, str) or not txt.strip():
            raise ModuleError("input 'csv_text' must be a non-empty string")
        return txt
    if not isinstance(b64, str) or not b64.strip():
        raise ModuleError("input 'csv_base64' must be a non-empty base64 string")
    try:
        raw = base64.b64decode(b64.strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ModuleError(f"input 'csv_base64' is not valid base64: {e}")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ModuleError(f"csv bytes are not valid UTF-8: {e}")


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=[",", ";", "\t", "|"])
        if dialect.delimiter in (",", ";", "\t", "|"):
            return dialect.delimiter
    except csv.Error:
        pass
    return ","


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    text = _get_text(inputs)
    delimiter = inputs.get("delimiter")
    if delimiter is not None:
        if not isinstance(delimiter, str) or len(delimiter) != 1:
            raise ModuleError("input 'delimiter' must be a single character")
    else:
        delimiter = _detect_delimiter(text)
    has_header = inputs.get("has_header", True)
    if not isinstance(has_header, bool):
        raise ModuleError("input 'has_header' must be a boolean")
    max_rows = inputs.get("max_rows", 10000)
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows <= 0:
        raise ModuleError("input 'max_rows' must be a positive integer")
    skip_empty = inputs.get("skip_empty", True)
    if not isinstance(skip_empty, bool):
        raise ModuleError("input 'skip_empty' must be a boolean")

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    raw_rows = []
    for row in reader:
        if skip_empty and not any(cell.strip() for cell in row):
            continue
        raw_rows.append(row)
    if not raw_rows:
        raise ModuleError("no data rows found in CSV input")

    if has_header:
        columns = [c.strip() for c in raw_rows[0]]
        data_rows = raw_rows[1:]
    else:
        width = max(len(r) for r in raw_rows)
        columns = [f"col_{i + 1}" for i in range(width)]
        data_rows = raw_rows

    truncated = len(data_rows) > max_rows
    data_rows = data_rows[:max_rows]
    rows = []
    for r in data_rows:
        padded = list(r) + [""] * (len(columns) - len(r))
        rows.append({columns[i]: padded[i] for i in range(len(columns))})

    ctx.log("csv_parse", {"rows": len(rows), "cols": len(columns),
                          "delimiter": delimiter})
    return {
        "status": "ok",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "delimiter": delimiter,
        "truncated": truncated,
        "char_count": len(text),
    }
