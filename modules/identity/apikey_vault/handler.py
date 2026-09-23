"""apikey_vault — encrypted-at-rest API key vault.

Crypto (v1, $0, stdlib only): master key from ctx.auth_get('vault_master')
-> PBKDF2-HMAC-SHA256 (200k rounds, per-key salt) -> HMAC-SHA256-CTR stream
cipher + HMAC authentication tag. Blobs live in ctx.memory.

HONEST CAVEAT: key management is the operator's job. Production should replace
'vault_master' with a KMS/HSM; this module documents that seam but fakes nothing.
Wrong master key -> decryption failure, never a silent wrong value.
"""
import base64
import hashlib
import hmac
import secrets

ROUNDS = 200_000
MEM_KEY = "apikey_vault:keys"
MASTER_PROVIDER = "vault_master"


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


# ---------- crypto ----------
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
        raise ModuleError("vault blob is corrupt")
    key = hashlib.pbkdf2_hmac("sha256", master, salt, ROUNDS, dklen=32)
    expect = hmac.new(key, b"aul-vault-v1" + nonce + ct, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, bundle.get("tag", "")):
        raise ModuleError("decryption failed: wrong master key or tampered blob")
    return bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce, len(ct))))


# ---------- capability ----------
def _master(ctx) -> bytes:
    return ctx.auth_get(MASTER_PROVIDER).encode("utf-8")  # raises AuthMissing


def _store(ctx):
    return ctx.memory_get(MEM_KEY) or {}


def _save(ctx, store):
    ctx.memory_set(MEM_KEY, store)


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ("store", "retrieve", "rotate", "revoke", "list"):
        raise ModuleError("action must be store, retrieve, rotate, revoke, or list")

    if action == "list":
        store = _store(ctx)
        keys = [{"key_name": k, "provider": v.get("provider", ""),
                 "last4": v.get("last4", ""), "version": v.get("version", 1)}
                for k, v in store.items()]
        ctx.log("apikey_vault", {"action": "list", "count": len(keys)})
        return {"action": action, "keys": keys}

    key_name = inputs.get("key_name")
    if not key_name or not isinstance(key_name, str):
        raise ModuleError("inputs.key_name is required (string)")
    master = _master(ctx)
    store = _store(ctx)

    if action in ("store", "rotate"):
        if action == "store" and key_name in store:
            raise ModuleError(f"key '{key_name}' already exists; use rotate")
        if action == "rotate" and key_name not in store:
            raise ModuleError(f"key '{key_name}' not found")
        key_value = inputs.get("key_value")
        if not key_value or not isinstance(key_value, str):
            raise ModuleError("inputs.key_value is required (string)")
        provider = inputs.get("provider", "") or ""
        ctx.approval_request(f"apikey_vault: {action} key '{key_name}'")
        blob = encrypt(master, key_value.encode("utf-8"))
        version = store.get(key_name, {}).get("version", 0) + 1
        store[key_name] = {"blob": blob, "provider": provider,
                           "last4": key_value[-4:] if len(key_value) >= 4 else "****",
                           "version": version}
        _save(ctx, store)
        ctx.log("apikey_vault", {"action": action, "key_name": key_name, "version": version})
        ctx.bill(0.001, f"apikey_vault {action} {key_name}")
        return {"action": action, "key_name": key_name, "ok": True, "version": version,
                "last4": store[key_name]["last4"], "provider": provider}

    if action == "retrieve":
        if key_name not in store:
            raise ModuleError(f"key '{key_name}' not found")
        value = decrypt(master, store[key_name]["blob"]).decode("utf-8")
        ctx.log("apikey_vault", {"action": "retrieve", "key_name": key_name})
        ctx.bill(0.001, f"apikey_vault retrieve {key_name}")
        return {"action": action, "key_name": key_name, "ok": True, "value": value,
                "provider": store[key_name].get("provider", ""),
                "version": store[key_name].get("version", 1)}

    # revoke
    if key_name not in store:
        raise ModuleError(f"key '{key_name}' not found")
    ctx.approval_request(f"apikey_vault: revoke key '{key_name}'")
    del store[key_name]
    _save(ctx, store)
    ctx.log("apikey_vault", {"action": "revoke", "key_name": key_name})
    ctx.bill(0.001, f"apikey_vault revoke {key_name}")
    return {"action": action, "key_name": key_name, "ok": True}
