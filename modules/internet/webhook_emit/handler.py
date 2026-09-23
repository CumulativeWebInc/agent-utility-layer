"""webhook_emit — signed JSON webhook POST.

Always requires ctx.approval_request (external send). HMAC-SHA256 signature
(X-Webhook-Signature: sha256=<hex>) when sign=true and a secret_provider is given.
"""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    url = inputs.get("url")
    event_name = inputs.get("event_name")
    payload = inputs.get("payload")
    if not url or not isinstance(url, str):
        raise ModuleError("inputs.url is required (string)")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("url must be an absolute http(s) URL")
    if not event_name or not isinstance(event_name, str):
        raise ModuleError("inputs.event_name is required (string)")
    if not isinstance(payload, dict):
        raise ModuleError("inputs.payload is required (object)")

    sign = inputs.get("sign", True)
    if not isinstance(sign, bool):
        raise ModuleError("sign must be a boolean")
    secret_provider = inputs.get("secret_provider")
    secret = None
    if sign:
        if not secret_provider:
            raise ModuleError("sign=true requires inputs.secret_provider")
        secret = ctx.auth_get(secret_provider)  # raises AuthMissing

    timeout = inputs.get("timeout_seconds", 10)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
        raise ModuleError("timeout_seconds must be a number in (0, 120]")

    ctx.approval_request(f"webhook_emit: POST {event_name} -> {url}")

    body = json.dumps({"event": event_name, "payload": payload}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    signature = None
    if sign:
        signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = signature

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            status = resp.status
            resp_body = resp.read(256 * 1024 + 1)
        delivered = 200 <= status < 300
    except urllib.error.HTTPError as e:
        status = e.code
        resp_body = e.read(256 * 1024 + 1)
        delivered = False
    except urllib.error.URLError as e:
        raise ModuleError(f"webhook POST failed: {e.reason}")
    except (TimeoutError, OSError) as e:
        raise ModuleError(f"webhook POST failed: {e}")
    elapsed_ms = (time.monotonic() - start) * 1000.0

    ctx.log("webhook_emit", {"event": event_name, "url": url, "status": status, "delivered": delivered})
    ctx.bill(0.001, f"webhook_emit {event_name}")
    return {
        "status": status,
        "delivered": delivered,
        "signature": signature,
        "response_body": resp_body.decode("utf-8", errors="replace"),
        "elapsed_ms": round(elapsed_ms, 2),
    }
