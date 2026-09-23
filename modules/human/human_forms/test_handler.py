import os
import sys

import pytest

import importlib.util as _ilu

_handler_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handler.py")
_spec = _ilu.spec_from_file_location("handler_under_test", _handler_path)
handler = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(handler)
from common import FakeCtx, ModuleError

INPUTS = {
    "title": "Bug report",
    "fields": [
        {"name": "summary", "type": "text", "label": "Summary", "required": True},
        {"name": "severity", "type": "choice", "options": ["low", "high"]},
        {"name": "count", "type": "number"},
    ],
}


def test_happy_path_creates_form():
    ctx = FakeCtx()
    result = handler.execute(dict(INPUTS), ctx)
    assert result["status"] == "created"
    assert result["form_id"].startswith("form_")
    assert result["field_count"] == 3
    assert result["preview_path"].endswith(result["form_id"])
    stored = ctx.memory_get("human_forms:%s" % result["form_id"])
    assert stored["title"] == "Bug report"
    assert ctx.bills[0][0] == 0.001


def test_no_approval_needed_for_creation():
    ctx = FakeCtx(approve=False)  # denial must not block pure creation
    result = handler.execute(dict(INPUTS), ctx)
    assert result["status"] == "created"


def test_missing_fields_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"title": "T"}, ctx)


def test_empty_fields_rejected():
    ctx = FakeCtx()
    with pytest.raises(ModuleError):
        handler.execute({"title": "T", "fields": []}, ctx)


def test_bad_field_type_rejected():
    ctx = FakeCtx()
    bad = dict(INPUTS)
    bad["fields"] = [{"name": "x", "type": "telepathy"}]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_choice_without_options_rejected():
    ctx = FakeCtx()
    bad = dict(INPUTS)
    bad["fields"] = [{"name": "pick", "type": "choice"}]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_duplicate_field_name_rejected():
    ctx = FakeCtx()
    bad = dict(INPUTS)
    bad["fields"] = [{"name": "a", "type": "text"}, {"name": "a", "type": "text"}]
    with pytest.raises(ModuleError):
        handler.execute(bad, ctx)


def test_output_schema_keys():
    ctx = FakeCtx()
    result = handler.execute(dict(INPUTS), ctx)
    assert set(result.keys()) == {"status", "form_id", "field_count", "preview_path"}
