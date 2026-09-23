"""sql_query — real SQL via stdlib sqlite3.

Read-only by default (SELECT/WITH/EXPLAIN/PRAGMA, single statement).
Anything else requires ctx.approval_request first; denial raises
ApprovalDenied and nothing executes.
"""

import base64
import binascii
import os
import re
import sqlite3
import tempfile


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_READ_FIRST = ("SELECT", "WITH", "EXPLAIN", "PRAGMA")
_WRITE_HINT = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|VACUUM|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


def _materialize_db(inputs) -> str:
    b64 = inputs.get("db_base64")
    path = inputs.get("db_path")
    if b64 is None and path is None:
        raise ModuleError("provide one of 'db_base64' or 'db_path'")
    if b64 is not None and path is not None:
        raise ModuleError("provide only one of 'db_base64' or 'db_path'")
    if b64 is not None:
        if not isinstance(b64, str) or not b64.strip():
            raise ModuleError("input 'db_base64' must be a non-empty base64 string")
        try:
            raw = base64.b64decode(b64.strip(), validate=True)
        except (binascii.Error, ValueError) as e:
            raise ModuleError(f"input 'db_base64' is not valid base64: {e}")
        if not raw.startswith(b"SQLite format 3\x00"):
            raise ModuleError("input 'db_base64' is not a SQLite database file")
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.write(raw)
        tmp.close()
        return tmp.name
    if not isinstance(path, str) or not path:
        raise ModuleError("input 'db_path' must be a non-empty string")
    if not os.path.isfile(path):
        raise ModuleError(f"db_path does not exist: {path}")
    return path


def _classify(query: str) -> str:
    stripped = query.strip().rstrip(";").strip()
    if not stripped:
        raise ModuleError("input 'query' must be a non-empty string")
    if ";" in stripped:
        raise ModuleError("only single-statement queries are allowed")
    first = stripped.split(None, 1)[0].upper()
    if first in _READ_FIRST:
        return "read"
    if _WRITE_HINT.search(stripped):
        return "write"
    raise ModuleError(
        f"unsupported statement '{first}': only SELECT/WITH/EXPLAIN/PRAGMA "
        "(read-only) or standard write statements (approval required) are allowed"
    )


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    query = inputs.get("query")
    if not isinstance(query, str):
        raise ModuleError("input 'query' must be a string")
    read_only = inputs.get("read_only", True)
    if not isinstance(read_only, bool):
        raise ModuleError("input 'read_only' must be a boolean")
    max_rows = inputs.get("max_rows", 1000)
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows <= 0:
        raise ModuleError("input 'max_rows' must be a positive integer")
    params = inputs.get("params", [])
    if not isinstance(params, (list, tuple)):
        raise ModuleError("input 'params' must be a list")

    kind = _classify(query)
    if read_only and kind == "write":
        raise ModuleError(
            "refusing write statement in read-only mode — set read_only=false "
            "and a human approval will be requested first"
        )
    if not read_only and kind == "write":
        # Destructive/write actions REQUIRE human approval first.
        ctx.approval_request(
            f"sql_query write statement: {query.strip()[:200]}", timeout_seconds=300
        )

    db_file = _materialize_db(inputs)
    tmp_created = inputs.get("db_base64") is not None
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro" if read_only else db_file,
                               uri=True)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, list(params))
            truncated = False
            if cur.description is None:  # write statement, no result set
                conn.commit()
                rows, columns = [], []
            else:
                columns = [d[0] for d in cur.description]
                fetched = cur.fetchmany(max_rows + 1)
                truncated = len(fetched) > max_rows
                rows = [dict(r) for r in fetched[:max_rows]]
            if not read_only:
                conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        raise ModuleError(f"sqlite error: {e}")
    finally:
        if tmp_created:
            try:
                os.unlink(db_file)
            except OSError:
                pass

    ctx.log("sql_query", {"kind": kind, "read_only": read_only,
                          "rows": len(rows)})
    return {
        "status": "ok",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "read_only": read_only,
    }
