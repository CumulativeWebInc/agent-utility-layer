"""http_request — real HTTP(S) request via stdlib urllib.

Write methods (POST/PUT/PATCH/DELETE) require ctx.approval_request.
"""
import time
import urllib.error
import urllib.parse
import urllib.request

SAFE_METHODS = {"GET", "HEAD"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ALL_METHODS = SAFE_METHODS | WRITE_METHODS


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    url = inputs.get("url")
    if not url or not isinstance(url, str):
        raise ModuleError("inputs.url is required (string)")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("url must be an absolute http(s) URL")
    method = str(inputs.get("method", "GET")).upper()
    if method not in ALL_METHODS:
        raise ModuleError(f"method must be one of {sorted(ALL_METHODS)}")
    timeout = inputs.get("timeout_seconds", 10)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 60):
        raise ModuleError("timeout_seconds must be a number in (0, 60]")
    max_bytes = inputs.get("max_response_bytes", 1048576)
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ModuleError("max_response_bytes must be a positive integer")
    headers = inputs.get("headers", {}) or {}
    if not isinstance(headers, dict):
        raise ModuleError("headers must be an object")
    body = inputs.get("body")
    if body is not None and not isinstance(body, str):
        raise ModuleError("body must be a string")
    return method, url, headers, body, float(timeout), max_bytes


def execute(inputs: dict, ctx) -> dict:
    method, url, headers, body, timeout, max_bytes = _validate(inputs)
    if method in WRITE_METHODS:
        ctx.approval_request(f"http_request: {method} {url} (destructive/external)")
    data = body.encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=dict(headers), method=method)

    start = time.monotonic()
    status, resp_headers, raw, final_url = _fetch(req, timeout, max_bytes)
    elapsed_ms = (time.monotonic() - start) * 1000.0

    body_text = raw.decode("utf-8", errors="replace")
    ctx.log("http_request", {"method": method, "url": url, "status": status})
    ctx.bill(0.001, f"http_request {method} {url}")
    return {
        "status": status,
        "headers": resp_headers,
        "body": body_text,
        "bytes_total": len(raw),
        "truncated": len(raw) >= max_bytes,
        "elapsed_ms": round(elapsed_ms, 2),
        "final_url": final_url,
    }


def _fetch(req, timeout, max_bytes):
    """Fetch with urllib's built-in redirect handling; final URL from resp.geturl()."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            headers = {k: v for k, v in resp.headers.items()}
            raw = resp.read(max_bytes + 1)[:max_bytes + 1]
            return status, headers, raw, resp.geturl()
    except urllib.error.HTTPError as e:
        raw = e.read(max_bytes + 1)[:max_bytes + 1]
        final = e.geturl() if hasattr(e, "geturl") else req.full_url
        return e.code, {k: v for k, v in e.headers.items()}, raw, final
    except urllib.error.URLError as e:
        raise ModuleError(f"request failed: {e.reason}")
    except (TimeoutError, OSError) as e:
        raise ModuleError(f"request failed: {e}")
