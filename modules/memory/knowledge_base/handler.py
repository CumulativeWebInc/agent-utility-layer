"""knowledge_base: document store with word-window chunking + lexical TF-IDF retrieval.

HONEST: retrieval is lexical (TF-IDF over terms), not semantic. For semantic
retrieval, embed the chunks and use the vector_search module.
"""
import json
import math
import os
import re
import sqlite3
import time
import uuid

_TOKEN = re.compile(r"[a-z0-9]+")


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
    path = os.path.join(_store_dir(ctx), "knowledge_base.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS documents ("
        " doc_id TEXT PRIMARY KEY, title TEXT NOT NULL, text TEXT NOT NULL,"
        " metadata_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL)")
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        " chunk_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, idx INTEGER NOT NULL,"
        " text TEXT NOT NULL)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (doc_id)")
    return con


def _tokens(text):
    return _TOKEN.findall(text.lower())


def _chunk_words(words, size, overlap):
    if size < 1:
        raise ModuleError("chunk_words must be >= 1")
    if not 0 <= overlap < size:
        raise ModuleError("overlap_words must satisfy 0 <= overlap < chunk_words")
    step = size - overlap
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + size]))
        if i + size >= len(words):
            break
        i += step
    return chunks


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("add_document", "get_document", "delete_document",
                  "list_documents", "retrieve"):
        raise ModuleError(
            "op must be one of add_document|get_document|delete_document|"
            "list_documents|retrieve")
    con = _db(ctx)
    try:
        if op == "add_document":
            text = inputs.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ModuleError("text must be a non-empty string")
            doc_id = inputs.get("doc_id") or uuid.uuid4().hex
            title = inputs.get("title", doc_id)
            if not isinstance(title, str):
                raise ModuleError("title must be a string")
            meta = inputs.get("metadata", {})
            if not isinstance(meta, dict):
                raise ModuleError("metadata must be an object")
            size = inputs.get("chunk_words", 200)
            overlap = inputs.get("overlap_words", 40)
            if not isinstance(size, int) or not isinstance(overlap, int):
                raise ModuleError("chunk_words/overlap_words must be integers")
            words = text.split()
            pieces = _chunk_words(words, size, overlap)
            now = time.time()
            con.execute(
                "INSERT OR REPLACE INTO documents"
                " (doc_id, title, text, metadata_json, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (doc_id, title, text, json.dumps(meta), now))
            con.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            for i, piece in enumerate(pieces):
                con.execute(
                    "INSERT INTO chunks (chunk_id, doc_id, idx, text)"
                    " VALUES (?, ?, ?, ?)",
                    (f"{doc_id}:{i}", doc_id, i, piece))
            con.commit()
            return {"status": "ok", "doc_id": doc_id, "chunks": len(pieces)}
        if op == "get_document":
            if not inputs.get("doc_id"):
                raise ModuleError("missing required input: doc_id")
            row = con.execute(
                "SELECT title, text, metadata_json, created_at FROM documents"
                " WHERE doc_id=?", (inputs["doc_id"],)).fetchone()
            if row is None:
                return {"status": "ok", "found": False}
            n = con.execute("SELECT COUNT(*) FROM chunks WHERE doc_id=?",
                            (inputs["doc_id"],)).fetchone()[0]
            return {"status": "ok", "found": True, "doc_id": inputs["doc_id"],
                    "title": row[0], "text": row[1],
                    "metadata": json.loads(row[2]), "created_at": row[3],
                    "chunks": n}
        if op == "delete_document":
            if not inputs.get("doc_id"):
                raise ModuleError("missing required input: doc_id")
            con.execute("DELETE FROM chunks WHERE doc_id=?", (inputs["doc_id"],))
            cur = con.execute("DELETE FROM documents WHERE doc_id=?",
                              (inputs["doc_id"],))
            con.commit()
            return {"status": "ok", "deleted": cur.rowcount}
        if op == "list_documents":
            rows = con.execute(
                "SELECT doc_id, title, created_at FROM documents"
                " ORDER BY created_at DESC LIMIT 200").fetchall()
            return {"status": "ok", "documents": [
                {"doc_id": r[0], "title": r[1], "created_at": r[2]} for r in rows]}
        # retrieve: TF-IDF over chunks
        query = inputs.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ModuleError("query must be a non-empty string")
        top_k = inputs.get("top_k", 5)
        if not isinstance(top_k, int) or top_k < 1:
            raise ModuleError("top_k must be a positive integer")
        rows = con.execute(
            "SELECT c.chunk_id, c.doc_id, c.text, d.title FROM chunks c"
            " JOIN documents d ON d.doc_id = c.doc_id").fetchall()
        if not rows:
            return {"status": "ok", "results": []}
        q_terms = _tokens(query)
        if not q_terms:
            return {"status": "ok", "results": []}
        # document frequency over chunks
        df = {}
        chunk_terms = []
        for _, _, text, _ in rows:
            terms = set(_tokens(text))
            chunk_terms.append(terms)
            for t in terms:
                df[t] = df.get(t, 0) + 1
        n = len(rows)
        scored = []
        for (chunk_id, doc_id, text, title), terms in zip(rows, chunk_terms):
            score = 0.0
            toks = _tokens(text)
            total = len(toks) or 1
            for t in set(q_terms):
                if t in terms:
                    tf = toks.count(t) / total
                    idf = math.log((n + 1) / (df[t] + 1)) + 1.0
                    score += tf * idf * q_terms.count(t)
            if score > 0:
                scored.append((score, chunk_id, doc_id, title, text))
        scored.sort(key=lambda t: t[0], reverse=True)
        return {"status": "ok", "results": [
            {"score": round(s, 6), "chunk_id": cid, "doc_id": did,
             "title": title, "text": text[:500]}
            for s, cid, did, title, text in scored[:top_k]]}
    finally:
        con.close()
