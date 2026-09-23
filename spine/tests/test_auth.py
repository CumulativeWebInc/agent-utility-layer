"""Tests for spine/auth.py (stdlib + pytest)."""

import os

import pytest

from auth import AuthError, KeyStore, key_fingerprint, keys_path


def test_issue_validate_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AUL_KEYS_FILE", str(tmp_path / "keys.json"))
    store = KeyStore()
    key = store.issue("dev", ["template:demo"])
    assert key.startswith("aul_")
    principal = store.validate(key)
    assert principal is not None
    assert principal["name"] == "dev"
    assert principal["permissions"] == ["template:demo"]
    assert "aul_" not in principal["id"]  # fingerprint only, never the key


def test_validate_bad_key_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("AUL_KEYS_FILE", str(tmp_path / "keys.json"))
    store = KeyStore()
    assert store.validate("aul_nope") is None
    assert store.validate("") is None
    assert store.validate(None) is None


def test_revoke_disables_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AUL_KEYS_FILE", str(tmp_path / "keys.json"))
    store = KeyStore()
    key = store.issue("dev")
    assert store.validate(key) is not None
    assert store.revoke(key) is True
    assert store.validate(key) is None
    assert store.revoke("aul_missing") is False


def test_keys_file_mode_600(tmp_path, monkeypatch):
    monkeypatch.setenv("AUL_KEYS_FILE", str(tmp_path / "keys.json"))
    store = KeyStore()
    store.issue("dev")
    assert oct(os.stat(str(tmp_path / "keys.json")).st_mode & 0o777) == "0o600"


def test_fingerprint_stable_and_not_key(tmp_path, monkeypatch):
    monkeypatch.setenv("AUL_KEYS_FILE", str(tmp_path / "keys.json"))
    key = KeyStore().issue("dev")
    fp1, fp2 = key_fingerprint(key), key_fingerprint(key)
    assert fp1 == fp2 and len(fp1) == 12 and fp1 not in key


def test_corrupt_keys_file_raises(tmp_path, monkeypatch):
    bad = tmp_path / "keys.json"
    bad.write_text("{not json")
    monkeypatch.setenv("AUL_KEYS_FILE", str(bad))
    with pytest.raises(AuthError):
        KeyStore().load()


def test_keys_path_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("AUL_KEYS_FILE", str(tmp_path / "custom.json"))
    assert keys_path() == str(tmp_path / "custom.json")
