"""Tests for knowledge_base."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_knowledge_base", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


DOC = ("The quick brown fox jumps over the lazy dog. " * 30).strip()
DOC2 = ("Cumulative Web Inc builds agent infrastructure software. " * 30).strip()


def test_add_chunks_document(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "add_document", "doc_id": "d1", "title": "Fox",
                 "text": DOC, "chunk_words": 50, "overlap_words": 10}, ctx)
    assert r["status"] == "ok" and r["chunks"] > 3
    g = execute({"op": "get_document", "doc_id": "d1"}, ctx)
    assert g["found"] is True and g["chunks"] == r["chunks"]


def test_retrieve_finds_relevant(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "add_document", "doc_id": "d1", "title": "Fox", "text": DOC}, ctx)
    execute({"op": "add_document", "doc_id": "d2", "title": "CWI", "text": DOC2}, ctx)
    r = execute({"op": "retrieve", "query": "agent infrastructure", "top_k": 3}, ctx)
    assert r["results"]
    assert r["results"][0]["doc_id"] == "d2"
    assert all("score" in x and x["score"] > 0 for x in r["results"])


def test_retrieve_no_match_empty(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "add_document", "doc_id": "d1", "title": "Fox", "text": DOC}, ctx)
    r = execute({"op": "retrieve", "query": "xylophone zebra quantum"}, ctx)
    assert r["results"] == []


def test_list_and_delete(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "add_document", "doc_id": "d1", "title": "Fox", "text": DOC}, ctx)
    lst = execute({"op": "list_documents"}, ctx)
    assert [d["doc_id"] for d in lst["documents"]] == ["d1"]
    d = execute({"op": "delete_document", "doc_id": "d1"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "get_document", "doc_id": "d1"}, ctx)["found"] is False
    assert execute({"op": "retrieve", "query": "fox"}, ctx)["results"] == []


def test_auto_doc_id(tmp_path):
    ctx = FakeCtx(tmp_path)
    r = execute({"op": "add_document", "title": "T", "text": "some words here"}, ctx)
    assert r["doc_id"]
    assert execute({"op": "get_document", "doc_id": r["doc_id"]}, ctx)["found"] is True


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "add_document", "title": "T", "text": "   "}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "add_document", "title": "T", "text": "words",
                 "chunk_words": 10, "overlap_words": 10}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "retrieve", "query": ""}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "retrieve", "query": "fox", "top_k": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
