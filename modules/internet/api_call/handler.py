"""api_call — JSON REST API call with a named credential injected as Bearer auth.

Credential comes from ctx.auth_get(auth_provider). Missing credential -> AuthMissing.
Non-GET methods require ctx.approval_request.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    auth_provider = inputs.get("auth_provider")
    base_url = inputs.get("base_url")
    endpoint = inputs.get("endpoint")
    for key, val in (("auth_provider", auth_provider), ("base_url", base_url), ("endpoint", endpoint)):
        if not val or not isinstance(val, str):
            raise ModuleError(f"inputs.{key} is required (string)")

    credential = ctx.auth_get(auth_provider)  # raises AuthMissing

    method = str(inputs.get("method", "GET")).upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        raise ModuleError("method must be GET/POST/PUT/PATCH/DELETE")
    if method in WRITE_METHODS:
        ctx.approval_request(f"api_call: {method} {base_url}{endpoint} (destructive/external)")

    query = inputs.get("query", {}) or {}
    if not isinstance(query, dict):
        raise ModuleError("query must be an object")
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)

    json_body = inputs.get("json_body")
    data = None
    headers = {"Authorization": f"Bearer {credential}", "Accept": "application/json"}
    if json_body is not None:
        if not isinstance(json_body, dict):
            raise ModuleError("json_body must be an object")
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    extra = inputs.get("headers", {}) or {}
    if not isinstance(extra, dict):
        raise ModuleError("headers must be an object")
    headers.update(extra)

    timeout = inputs.get("timeout_seconds", 15)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
        raise ModuleError("timeout_seconds must be a number in (0, 120]")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            status = resp.status
            raw = resp.read(4 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read(4 * 1024 * 1024 + 1)
    except urllib.error.URLError as e:
        raise ModuleError(f"api call failed: {e.reason}")
    except (TimeoutError, OSError) as e:
        raise ModuleError(f"api call failed: {e}")
    elapsed_ms = (time.monotonic() - start) * 1000.0

    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        parsed = text  # non-JSON returned as raw text, honestly

    # Never log the credential or full bodies that may contain secrets.
    ctx.log("api_call", {"method": method, "base_url": base_url, "endpoint": endpoint, "status": status})
    ctx.bill(0.001, f"api_call {method} {endpoint}")
    return {
        "status": status,
        "data": parsed,
        "elapsed_ms": round(elapsed_ms, 2),
        "bytes_total": len(raw),
    }
