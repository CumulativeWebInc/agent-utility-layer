"""Tests for vector_search."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_vector_search", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def _seed(ctx):
    execute({"op": "upsert", "id": "a", "embedding": [1.0, 0.0, 0.0],
             "metadata": {"label": "x"}}, ctx)
    execute({"op": "upsert", "id": "b", "embedding": [0.0, 1.0, 0.0]}, ctx)
    execute({"op": "upsert", "id": "c", "embedding": [0.9, 0.1, 0.0]}, ctx)


def test_search_ranking(tmp_path):
    ctx = FakeCtx(tmp_path)
    _seed(ctx)
    r = execute({"op": "search", "query_embedding": [1.0, 0.0, 0.0], "top_k": 2}, ctx)
    ids = [x["id"] for x in r["results"]]
    assert ids == ["a", "c"]
    assert r["results"][0]["score"] == pytest.approx(1.0)
    assert r["results"][1]["score"] < 1.0


def test_upsert_get_delete_count(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "upsert", "id": "a", "embedding": [1, 2, 3]}, ctx)
    g = execute({"op": "get", "id": "a"}, ctx)
    assert g["found"] is True and g["embedding"] == [1.0, 2.0, 3.0]
    assert execute({"op": "count"}, ctx)["count"] == 1
    d = execute({"op": "delete", "id": "a"}, ctx)
    assert d["deleted"] == 1
    assert execute({"op": "get", "id": "a"}, ctx)["found"] is False
    assert execute({"op": "count"}, ctx)["count"] == 0


def test_dim_mismatch_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "upsert", "id": "a", "embedding": [1, 2, 3]}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "upsert", "id": "b", "embedding": [1, 2]}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "search", "query_embedding": [1, 2, 3, 4]}, ctx)


def test_bad_vectors_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "upsert", "id": "a", "embedding": []}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "upsert", "id": "a", "embedding": ["x", "y"]}, ctx)


def test_zero_vector_search_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "upsert", "id": "a", "embedding": [1, 0]}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "search", "query_embedding": [0, 0]}, ctx)


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "search", "query_embedding": [1, 2], "top_k": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "upsert", "embedding": [1, 2]}, ctx)  # missing id
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
