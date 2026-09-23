"""Tests for error_recovery."""
import importlib.util
import os
import sys
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aul_handler_error_recovery", os.path.join(_HERE, "handler.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
execute = _mod.execute
ModuleError = _mod.ModuleError

class FakeCtx:
    def __init__(self, tmp_path):
        self.store_dir = str(tmp_path)


def test_register_suggest(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "register", "error_class": "rate_limit",
             "match_regex": r"429|rate limit",
             "steps": ["back off 60s", "retry with jitter"]}, ctx)
    s = execute({"op": "suggest", "error_class": "rate_limit",
                 "message": "got 429 from provider"}, ctx)
    assert len(s["suggestions"]) == 1
    assert s["suggestions"][0]["steps"] == ["back off 60s", "retry with jitter"]


def test_suggest_regex_miss(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "register", "error_class": "rate_limit",
             "match_regex": r"429", "steps": ["wait"]}, ctx)
    s = execute({"op": "suggest", "error_class": "rate_limit",
                 "message": "connection refused"}, ctx)
    assert s["suggestions"] == []


def test_suggest_all_classes(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "register", "error_class": "a", "steps": ["s1"]}, ctx)
    execute({"op": "register", "error_class": "b", "steps": ["s2"]}, ctx)
    s = execute({"op": "suggest"}, ctx)
    assert {x["error_class"] for x in s["suggestions"]} == {"a", "b"}


def test_list_and_log_recovery(tmp_path):
    ctx = FakeCtx(tmp_path)
    execute({"op": "register", "error_class": "a", "steps": ["s1"]}, ctx)
    lst = execute({"op": "list"}, ctx)
    assert [p["error_class"] for p in lst["playbooks"]] == ["a"]
    r = execute({"op": "log_recovery", "error_class": "a", "action": "retried",
                 "outcome": "ok"}, ctx)
    assert r["status"] == "ok"


def test_invalid_regex_rejected(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "register", "error_class": "a",
                 "match_regex": r"([", "steps": ["s"]}, ctx)


def test_invalid_inputs(tmp_path):
    ctx = FakeCtx(tmp_path)
    with pytest.raises(ModuleError):
        execute({"op": "register", "error_class": "a", "steps": []}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "register", "error_class": "a", "steps": "nope"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "log_recovery", "error_class": "a"}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "suggest", "message": 123}, ctx)
    with pytest.raises(ModuleError):
        execute({"op": "nope"}, ctx)
