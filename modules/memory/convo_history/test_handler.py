"""Tests for convo_history."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_convo_history", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def _seed(ctx, sid="s1"):
    execute({"op": "append", "session_id": sid, "user_id": "u1",
             "role": "user", "content": "hello world"}, ctx)
    execute({"op": "append", "session_id": sid, "user_id": "u1",
             "role": "assistant", "content": "hi there"}, ctx)


def test_append_history_order(tmp_path):
    ctx = FakeCtx(tmp_path)
    _seed(ctx)
    h = execute({"op": "history", "session_id": "s1"}, ctx)
    assert len(h["messages"]) == 2
    assert [m["role"] for m in h["messages"]] == ["user", "assistant"]
    assert all(m["id"] for m in h["messages"])


def test_history_limit(tmp_path):
    ctx = FakeCtx(tmp_path)
    _seed(ctx)
    h = execute({"op": "history", "session_id": "s1", "limit": 1}, ctx)
    assert len(h["messages"]) == 1


def test_sessions(tmp_path):
    ctx = FakeCtx(tmp_path)
    _seed(ctx, "s1")
    _seed(ctx, "s2")
    s = execute({"op": "sessions", "user_id": "u1"}, ctx)
    assert s["sessions"] == ["s1", "s2"]


def test_search(tmp_path):
    ctx = FakeCtx(tmp_path)
    _seed(ctx)
    r = execute({"op": "search", "query": "hello"}, ctx)
    assert len(r["messages"]) == 1
    assert r["messages"][0]["role"] == "user"


def test_clear(tmp_path):
    ctx = FakeCtx(tmp_path)
    _seed(ctx)
    c = execute({"op": "clear", "session_id": "s1"}, ctx)
    assert c["cleared"] == 2
    assert execute({"op": "history", "session_id": "s1"}, ctx)["messages"] == []


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "append", "session_id": "s1", "role": "alien",
                 "content": "x"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "append", "session_id": "s1", "role": "user",
                 "content": ""}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "history", "session_id": "s1", "limit": 0}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "search"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
