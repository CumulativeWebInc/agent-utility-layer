"""Tests for spine/permissions.py (stdlib + pytest)."""

import pytest

import permissions
from permissions import PermissionDenied, declare, enforce, is_declared, missing


def test_exact_grant():
    assert missing(["email:send"], ["email:send"]) == []


def test_wildcard_grant():
    assert missing(["*"], ["email:send", "money:charge"]) == []


def test_scope_wildcard_grant():
    assert missing(["email:*"], ["email:send"]) == []
    assert missing(["email:*"], ["sms:send"]) == ["sms:send"]


def test_missing_reported():
    assert missing(["email:send"], ["email:send", "sms:send"]) == ["sms:send"]


def test_enforce_raises_with_names():
    with pytest.raises(PermissionDenied) as exc:
        enforce({"name": "agent1", "permissions": []}, ["email:send"])
    assert "email:send" in str(exc.value)


def test_enforce_passes():
    enforce({"name": "a", "permissions": ["*"]}, ["email:send"])  # no raise


def test_declare_and_lookup():
    declare("test:thing", "a test permission")
    assert is_declared("test:thing")
    assert not is_declared("test:nope")


def test_declare_rejects_bad_shape():
    with pytest.raises(ValueError):
        declare("noscope", "bad")
