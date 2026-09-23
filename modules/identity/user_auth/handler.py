"""user_auth — register / verify / rotate user credentials.

Credentials stored as PBKDF2-HMAC-SHA256 hashes (200k rounds, per-user salt)
in ctx.memory. register requires ctx.approval_request. This is application-level
auth; the spine's API-key auth (spine/auth.py) is a separate layer.
"""
import hashlib
import hmac
import secrets

ROUNDS = 200_000
MIN_LEN = 12
MEM_KEY = "user_auth:users"


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _hash(credential: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", credential.encode("utf-8"), salt, ROUNDS).hex()


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ("register", "verify", "rotate"):
        raise ModuleError("action must be register, verify, or rotate")
    username = inputs.get("username")
    credential = inputs.get("credential")
    if not username or not isinstance(username, str):
        raise ModuleError("inputs.username is required (string)")
    if not credential or not isinstance(credential, str):
        raise ModuleError("inputs.credential is required (string)")
    if len(username) > 128:
        raise ModuleError("username too long")

    users = ctx.memory_get(MEM_KEY) or {}

    if action == "register":
        if username in users:
            raise ModuleError(f"username '{username}' already registered")
        _check_strength(credential)
        ctx.approval_request(f"user_auth: register identity record for '{username}'")
        salt = secrets.token_bytes(16)
        users[username] = {"salt": salt.hex(), "hash": _hash(credential, salt)}
        ctx.memory_set(MEM_KEY, users)
        ctx.log("user_auth", {"action": "register", "username": username})
        ctx.bill(0.001, f"user_auth register {username}")
        return {"action": action, "username": username, "ok": True,
                "message": "registered"}

    if username not in users:
        raise ModuleError("unknown username")
    rec = users[username]
    good = hmac.compare_digest(
        _hash(credential, bytes.fromhex(rec["salt"])), rec["hash"])

    if action == "verify":
        ctx.log("user_auth", {"action": "verify", "username": username, "ok": good})
        ctx.bill(0.001, f"user_auth verify {username}")
        if not good:
            raise ModuleError("invalid credential")
        return {"action": action, "username": username, "ok": True,
                "message": "credential verified"}

    # rotate
    if not good:
        raise ModuleError("invalid current credential")
    new_credential = inputs.get("new_credential")
    if not new_credential or not isinstance(new_credential, str):
        raise ModuleError("inputs.new_credential is required (string) for rotate")
    _check_strength(new_credential)
    salt = secrets.token_bytes(16)
    users[username] = {"salt": salt.hex(), "hash": _hash(new_credential, salt)}
    ctx.memory_set(MEM_KEY, users)
    ctx.log("user_auth", {"action": "rotate", "username": username})
    ctx.bill(0.001, f"user_auth rotate {username}")
    return {"action": action, "username": username, "ok": True,
            "message": "credential rotated"}


def _check_strength(credential: str):
    if len(credential) < MIN_LEN:
        raise ModuleError(f"credential must be at least {MIN_LEN} characters")
