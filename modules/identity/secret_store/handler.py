"""secret_store — versioned encrypted secret storage.

Same crypto construction as apikey_vault (PBKDF2 -> HMAC-SHA256-CTR + HMAC tag,
master key from ctx.auth_get('vault_master')), separate namespace.
Every store creates a new version; history keeps the last 10; rollback points
the current pointer at an older version (history is never deleted).
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

ROUNDS = 200_000
MEM_KEY = "secret_store:secrets"
MASTER_PROVIDER = "vault_master"
HISTORY_KEEP = 10


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hmac.new(key, nonce + ctr.to_bytes(8, "big"), hashlib.sha256).digest()
        ctr += 1
    return bytes(out[:n])


def encrypt(master: bytes, plaintext: bytes) -> dict:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", master, salt, ROUNDS, dklen=32)
    ct = bytes(a ^ b for a, b in zip(plaintext, _keystream(key, nonce, len(plaintext))))
    tag = hmac.new(key, b"aul-vault-v1" + nonce + ct, hashlib.sha256).hexdigest()
    return {"salt": _b64e(salt), "nonce": _b64e(nonce), "ct": _b64e(ct), "tag": tag}


def decrypt(master: bytes, bundle: dict) -> bytes:
    try:
        salt, nonce, ct = _b64d(bundle["salt"]), _b64d(bundle["nonce"]), _b64d(bundle["ct"])
    except Exception:
        raise ModuleError("secret blob is corrupt")
    key = hashlib.pbkdf2_hmac("sha256", master, salt, ROUNDS, dklen=32)
    expect = hmac.new(key, b"aul-vault-v1" + nonce + ct, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, bundle.get("tag", "")):
        raise ModuleError("decryption failed: wrong master key or tampered blob")
    return bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce, len(ct))))


def _now():
    return datetime.now(timezone.utc).isoformat()


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ("store", "retrieve", "list", "versions", "rollback"):
        raise ModuleError("action must be store, retrieve, list, versions, or rollback")
    master = ctx.auth_get(MASTER_PROVIDER).encode("utf-8")  # raises AuthMissing
    store = ctx.memory_get(MEM_KEY) or {}

    if action == "list":
        names = [{"name": k, "current_version": v["current"],
                  "version_count": len(v["history"])} for k, v in store.items()]
        ctx.log("secret_store", {"action": "list", "count": len(names)})
        return {"action": action, "names": names}

    name = inputs.get("name")
    if not name or not isinstance(name, str):
        raise ModuleError("inputs.name is required (string)")
    rec = store.get(name)

    if action == "store":
        value = inputs.get("value")
        if not value or not isinstance(value, str):
            raise ModuleError("inputs.value is required (string)")
        ctx.approval_request(f"secret_store: store secret '{name}'")
        version = (rec["current"] if rec else 0) + 1
        entry = {"version": version, "blob": encrypt(master, value.encode("utf-8")),
                 "stored_at": _now()}
        history = (rec["history"] if rec else []) + [entry]
        store[name] = {"current": version, "history": history[-HISTORY_KEEP:]}
        ctx.memory_set(MEM_KEY, store)
        ctx.log("secret_store", {"action": "store", "name": name, "version": version})
        ctx.bill(0.001, f"secret_store store {name}")
        return {"action": action, "name": name, "ok": True, "version": version}

    if rec is None:
        raise ModuleError(f"secret '{name}' not found")

    if action == "retrieve":
        version = inputs.get("version", rec["current"])
        if not isinstance(version, int):
            raise ModuleError("version must be an integer")
        entry = next((e for e in rec["history"] if e["version"] == version), None)
        if entry is None:
            raise ModuleError(f"version {version} not found for '{name}'")
        value = decrypt(master, entry["blob"]).decode("utf-8")
        ctx.log("secret_store", {"action": "retrieve", "name": name, "version": version})
        ctx.bill(0.001, f"secret_store retrieve {name}")
        return {"action": action, "name": name, "ok": True, "value": value, "version": version}

    if action == "versions":
        versions = [{"version": e["version"], "stored_at": e["stored_at"],
                     "current": e["version"] == rec["current"]} for e in rec["history"]]
        ctx.log("secret_store", {"action": "versions", "name": name})
        return {"action": action, "name": name, "versions": versions}

    # rollback
    version = inputs.get("version")
    if not isinstance(version, int):
        raise ModuleError("inputs.version is required (integer) for rollback")
    if not any(e["version"] == version for e in rec["history"]):
        raise ModuleError(f"version {version} not found for '{name}'")
    ctx.approval_request(f"secret_store: rollback '{name}' to version {version}")
    rec["current"] = version
    ctx.memory_set(MEM_KEY, store)
    ctx.log("secret_store", {"action": "rollback", "name": name, "version": version})
    ctx.bill(0.001, f"secret_store rollback {name}")
    return {"action": action, "name": name, "ok": True, "version": version}
