"""data_transform — real JSON record pipelines. stdlib only.

Ops: filter, select, rename, sort, limit, group_by, flatten.
Filter/where supports $eq/$ne/$gt/$gte/$lt/$lte/$in/$contains (bare value = $eq).
"""


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_OPS = {
    "$eq": lambda a, b: a == b,
    "$ne": lambda a, b: a != b,
    "$gt": lambda a, b: a is not None and b is not None and a > b,
    "$gte": lambda a, b: a is not None and b is not None and a >= b,
    "$lt": lambda a, b: a is not None and b is not None and a < b,
    "$lte": lambda a, b: a is not None and b is not None and a <= b,
    "$in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
    "$contains": lambda a, b: isinstance(a, str) and b in a,
}


def _where_matches(row: dict, where: dict) -> bool:
    for field, cond in where.items():
        val = row.get(field)
        if isinstance(cond, dict) and cond and all(k.startswith("$") for k in cond):
            for op, operand in cond.items():
                if op not in _OPS:
                    raise ModuleError(f"unknown where operator '{op}'")
                try:
                    if not _OPS[op](val, operand):
                        return False
                except TypeError:
                    return False
        elif val != cond:
            return False
    return True


def _op_filter(rows, spec):
    where = spec.get("where")
    if not isinstance(where, dict):
        raise ModuleError("filter op needs {'where': {...}}")
    return [r for r in rows if _where_matches(r, where)]


def _op_select(rows, spec):
    fields = spec.get("fields")
    if not isinstance(fields, list) or not fields or not all(
        isinstance(f, str) for f in fields
    ):
        raise ModuleError("select op needs {'fields': ['a', 'b', ...]}")
    return [{f: r.get(f) for f in fields} for r in rows]


def _op_rename(rows, spec):
    mapping = spec.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        raise ModuleError("rename op needs {'mapping': {old: new, ...}}")
    out = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            nr[mapping.get(k, k)] = v
        out.append(nr)
    return out


def _op_sort(rows, spec):
    by = spec.get("by")
    if not isinstance(by, str):
        raise ModuleError("sort op needs {'by': 'field'}")
    desc = bool(spec.get("desc", False))
    try:
        return sorted(rows, key=lambda r: (r.get(by) is None, r.get(by)),
                      reverse=desc)
    except TypeError as e:
        raise ModuleError(f"sort failed (mixed types in '{by}'): {e}")


def _op_limit(rows, spec):
    n = spec.get("n")
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ModuleError("limit op needs {'n': non-negative int}")
    return rows[:n]


def _agg(values, fn):
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if fn == "count":
        return len(values)
    if fn in ("sum", "avg", "min", "max") and len(nums) != len(values):
        raise ModuleError(f"agg '{fn}' needs numeric values, got non-numeric")
    if fn == "sum":
        return sum(nums)
    if fn == "avg":
        return sum(nums) / len(nums) if nums else 0
    if fn == "min":
        return min(nums) if nums else None
    if fn == "max":
        return max(nums) if nums else None
    raise ModuleError(f"unknown agg fn '{fn}' (want count/sum/avg/min/max)")


def _op_group_by(rows, spec):
    field = spec.get("field")
    aggs = spec.get("aggs")
    if not isinstance(field, str):
        raise ModuleError("group_by op needs {'field': 'f', 'aggs': [...]}")
    if not isinstance(aggs, list) or not aggs:
        raise ModuleError("group_by op needs a non-empty 'aggs' list")
    groups = {}
    for r in rows:
        groups.setdefault(r.get(field), []).append(r)
    out = []
    for key, members in groups.items():
        agg_row = {field: key}
        for a in aggs:
            if not isinstance(a, dict) or "fn" not in a:
                raise ModuleError("each agg needs {'fn': ..., 'field': ..., 'as': ...}")
            fn = a["fn"]
            f = a.get("field")
            alias = a.get("as", f"{fn}_{f or 'n'}")
            values = [m.get(f) for m in members] if f else members
            agg_row[alias] = _agg(values, fn)
        out.append(agg_row)
    return out


def _op_flatten(rows, spec):
    sep = spec.get("sep", ".")
    if not isinstance(sep, str):
        raise ModuleError("flatten op 'sep' must be a string")
    out = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    nr[f"{k}{sep}{sk}"] = sv
            else:
                nr[k] = v
        out.append(nr)
    return out


_DISPATCH = {
    "filter": _op_filter,
    "select": _op_select,
    "rename": _op_rename,
    "sort": _op_sort,
    "limit": _op_limit,
    "group_by": _op_group_by,
    "flatten": _op_flatten,
}


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    data = inputs.get("data")
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ModuleError("input 'data' must be a list of objects")
    pipeline = inputs.get("pipeline")
    if not isinstance(pipeline, list) or not pipeline or not all(
        isinstance(s, dict) for s in pipeline
    ):
        raise ModuleError("input 'pipeline' must be a non-empty list of op objects")

    rows = [dict(r) for r in data]
    applied = []
    for i, spec in enumerate(pipeline):
        op = spec.get("op")
        if op not in _DISPATCH:
            raise ModuleError(
                f"pipeline[{i}]: unknown op '{op}'. valid: "
                + ", ".join(sorted(_DISPATCH))
            )
        rows = _DISPATCH[op](rows, spec)
        applied.append(op)

    ctx.log("data_transform", {"ops": applied, "rows": len(rows)})
    return {
        "status": "ok",
        "rows": rows,
        "row_count": len(rows),
        "ops_applied": applied,
    }
