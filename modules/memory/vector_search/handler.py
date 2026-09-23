"""vector_search: vector similarity store with real cosine-similarity top-k search.

HONEST: no embedding model is bundled. The caller MUST supply embedding vectors
(e.g. from sentence-transformers, fastembed, or an embedding API). This module
stores vectors and computes exact brute-force cosine similarity.
"""
import json
import math
import os
import sqlite3


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _store_dir(ctx):
    d = getattr(ctx, "store_dir", None) or os.environ.get("AUL_STORE_DIR") \
        or os.path.expanduser("~/.aul/data")
    os.makedirs(d, exist_ok=True)
    return d


def _db(ctx):
    path = os.path.join(_store_dir(ctx), "vector_search.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS vectors ("
        " id TEXT PRIMARY KEY, embedding_json TEXT NOT NULL,"
        " metadata_json TEXT NOT NULL DEFAULT '{}')"
    )
    return con


def _check_vec(v, what):
    if not isinstance(v, list) or not v:
        raise ModuleError(f"{what} must be a non-empty list of numbers")
    if not all(isinstance(x, (int, float)) for x in v):
        raise ModuleError(f"{what} must be a non-empty list of numbers")
    return [float(x) for x in v]


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        raise ModuleError("zero-magnitude embedding vector is not searchable")
    return dot / (na * nb)


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("upsert", "get", "delete", "search", "count"):
        raise ModuleError("op must be one of upsert|get|delete|search|count")
    con = _db(ctx)
    try:
        if op == "upsert":
            if not inputs.get("id"):
                raise ModuleError("missing required input: id")
            vec = _check_vec(inputs.get("embedding"), "embedding")
            meta = inputs.get("metadata", {})
            if not isinstance(meta, dict):
                raise ModuleError("metadata must be an object")
            first = con.execute("SELECT embedding_json FROM vectors LIMIT 1").fetchone()
            if first is not None:
                dim = len(json.loads(first[0]))
                if len(vec) != dim:
                    raise ModuleError(
                        f"dimension mismatch: store uses dim {dim}, got {len(vec)}")
            con.execute(
                "INSERT OR REPLACE INTO vectors (id, embedding_json, metadata_json)"
                " VALUES (?, ?, ?)",
                (inputs["id"], json.dumps(vec), json.dumps(meta)))
            con.commit()
            return {"status": "ok", "id": inputs["id"], "dim": len(vec)}
        if op == "get":
            if not inputs.get("id"):
                raise ModuleError("missing required input: id")
            row = con.execute(
                "SELECT embedding_json, metadata_json FROM vectors WHERE id=?",
                (inputs["id"],)).fetchone()
            if row is None:
                return {"status": "ok", "found": False}
            return {"status": "ok", "found": True, "id": inputs["id"],
                    "embedding": json.loads(row[0]),
                    "metadata": json.loads(row[1])}
        if op == "delete":
            if not inputs.get("id"):
                raise ModuleError("missing required input: id")
            cur = con.execute("DELETE FROM vectors WHERE id=?", (inputs["id"],))
            con.commit()
            return {"status": "ok", "deleted": cur.rowcount}
        if op == "count":
            n = con.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            return {"status": "ok", "count": n}
        # search
        q = _check_vec(inputs.get("query_embedding"), "query_embedding")
        top_k = inputs.get("top_k", 5)
        if not isinstance(top_k, int) or top_k < 1:
            raise ModuleError("top_k must be a positive integer")
        rows = con.execute("SELECT id, embedding_json, metadata_json FROM vectors").fetchall()
        if rows:
            dim = len(json.loads(rows[0][1]))
            if len(q) != dim:
                raise ModuleError(
                    f"dimension mismatch: store uses dim {dim}, got {len(q)}")
        scored = []
        for vid, ej, mj in rows:
            scored.append((vid, _cosine(q, json.loads(ej)), json.loads(mj)))
        scored.sort(key=lambda t: t[1], reverse=True)
        return {"status": "ok", "results": [
            {"id": vid, "score": s, "metadata": mj}
            for vid, s, mj in scored[:top_k]]}
    finally:
        con.close()
