"""Tests for spine/registry.py (stdlib + pytest)."""

import json
import os

import pytest

from registry import load_modules, validate_capability, validate_inputs

GOOD = {
    "name": "mod_x",
    "provisional": True,
    "pillar": "data",
    "version": "0.1.0",
    "description": "x",
    "permissions": ["ui:render"],
    "inputs_schema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
    "outputs_schema": {"type": "object", "properties": {"r": {"type": "string"}}},
    "setup_price_usd": 1.0,
    "price_per_execution_usd": 0.001,
}


def test_validate_good():
    errors, _warnings = validate_capability(GOOD)
    assert errors == []


def test_validate_missing_fields():
    errors, _ = validate_capability({"name": "x"})
    assert any("pillar" in e for e in errors)


def test_validate_bad_version_and_price():
    bad = dict(GOOD, version="1", setup_price_usd=-1)
    errors, _ = validate_capability(bad)
    assert any("version" in e for e in errors)
    assert any("setup_price_usd" in e for e in errors)


def test_validate_undeclared_permission_warns():
    errors, warnings = validate_capability(dict(GOOD, permissions=["zzz:new"]))
    assert errors == []
    assert any("zzz:new" in w for w in warnings)


def _write_module(root, pillar, module, capability=None, with_handler=True):
    d = os.path.join(root, "modules", pillar, module)
    os.makedirs(d)
    if capability is not None:
        with open(os.path.join(d, "capability.json"), "w") as fh:
            json.dump(capability, fh)
    if with_handler:
        with open(os.path.join(d, "handler.py"), "w") as fh:
            fh.write("def execute(inputs, ctx):\n    return {}\n")


def test_load_modules_states(tmp_path):
    root = str(tmp_path)
    _write_module(root, "data", "good_mod", dict(GOOD, name="good_mod"))
    _write_module(root, "data", "no_handler", dict(GOOD, name="no_handler"), with_handler=False)
    _write_module(root, "data", "bad_cap", {"name": "bad_cap"})
    _write_module(root, "data", "no_cap", None)
    reg = load_modules(root)
    assert reg.modules["good_mod"].live
    assert reg.modules["no_handler"].state == "skeleton"
    assert reg.modules["bad_cap"].state == "invalid"
    assert reg.modules["no_cap"].state == "invalid"
    assert set(reg.live_modules()) == {"good_mod"}


def test_load_modules_empty_root(tmp_path):
    assert load_modules(str(tmp_path)).modules == {}


def test_validate_inputs_happy():
    schema = GOOD["inputs_schema"]
    assert validate_inputs(schema, {"q": "hi"}) == []


def test_validate_inputs_missing_required():
    assert validate_inputs(GOOD["inputs_schema"], {}) != []


def test_validate_inputs_wrong_type_and_unknown():
    errors = validate_inputs(GOOD["inputs_schema"], {"q": 5, "zzz": 1})
    assert len(errors) == 2


def test_validate_inputs_constraints():
    schema = {"type": "object",
              "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 5},
                             "s": {"type": "string", "minLength": 2},
                             "c": {"type": "string", "enum": ["a", "b"]}},
              "required": []}
    assert validate_inputs(schema, {"n": 0, "s": "x", "c": "z"})
    assert validate_inputs(schema, {"n": 3, "s": "xy", "c": "a"}) == []
    assert validate_inputs(schema, {"n": True})  # bool is not integer here
