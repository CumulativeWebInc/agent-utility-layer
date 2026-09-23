"""API-key authentication for the Agent Utility Layer exec API.

Keys live in a JSON file OUTSIDE the repo. Default:
  ~/.config/agent-utility-layer/keys.json
Override with env AUL_KEYS_FILE.

This module never logs, prints, or returns raw key values — only 12-char
fingerprints (sha256 prefix). Never commit the keys file.
"""

import hashlib
import json
import os
import secrets
import tempfile
import time

KEYS_ENV = "AUL_KEYS_FILE"
DEFAULT_KEYS_PATH = os.path.expanduser("~/.config/agent-utility-layer/keys.json")


class AuthError(Exception):
    """Raised for auth configuration problems (not for bad keys)."""


def keys_path() -> str:
    return os.environ.get(KEYS_ENV, DEFAULT_KEYS_PATH)


def key_fingerprint(key: str) -> str:
    """Public fingerprint of a key — safe to log. Never log the key itself."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


class KeyStore:
    """Load/validate/issue API keys. Keys are opaque bearer tokens."""

    def __init__(self, path: str | None = None):
        self.path = path or keys_path()

    def _blank(self) -> dict:
        return {"keys": {}}

    def load(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict) or not isinstance(data.get("keys"), dict):
                raise AuthError(f"keys file has bad shape: {self.path}")
            return data
        except FileNotFoundError:
            return self._blank()
        except json.JSONDecodeError as exc:
            raise AuthError(f"keys file is not valid JSON: {self.path}: {exc}")

    def save(self, data: dict) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory or None, prefix=".keys-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def validate(self, key: str) -> dict | None:
        """Return the principal dict for a valid, enabled key; else None.

        Principal: {"id", "name", "permissions", "created", "enabled"}.
        The raw key is never included in the returned principal.
        """
        if not key or not isinstance(key, str):
            return None
        record = self.load()["keys"].get(key)
        if not record or not record.get("enabled", True):
            return None
        return {
            "id": key_fingerprint(key),
            "name": record.get("name", ""),
            "permissions": list(record.get("permissions", [])),
            "created": record.get("created", ""),
            "enabled": True,
        }

    def issue(self, name: str, permissions: list[str] | None = None) -> str:
        """Create a key, persist it, return the RAW key (shown once)."""
        key = "aul_" + secrets.token_urlsafe(32)
        data = self.load()
        data["keys"][key] = {
            "name": name,
            "permissions": list(permissions or []),
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "enabled": True,
        }
        self.save(data)
        return key

    def revoke(self, key: str) -> bool:
        data = self.load()
        if key in data["keys"]:
            data["keys"][key]["enabled"] = False
            self.save(data)
            return True
        return False
