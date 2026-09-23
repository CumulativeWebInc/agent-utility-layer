"""site_monitor — single uptime check with state-change detection across runs.

Previous state is stored in ctx.memory under f"site_monitor:{monitor_id}".
One check per execution; pair with Crew H job_schedule for intervals.
"""
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


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
    if not url or not isinstance(url, str):
        raise ModuleError("inputs.url is required (string)")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("url must be an absolute http(s) URL")
    expected_status = inputs.get("expected_status", 200)
    if not isinstance(expected_status, int):
        raise ModuleError("expected_status must be an integer")
    expected_text = inputs.get("expected_text")
    if expected_text is not None and not isinstance(expected_text, str):
        raise ModuleError("expected_text must be a string")
    timeout = inputs.get("timeout_seconds", 10)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
        raise ModuleError("timeout_seconds must be a number in (0, 120]")
    monitor_id = inputs.get("monitor_id") or url
    if not isinstance(monitor_id, str):
        raise ModuleError("monitor_id must be a string")

    mem_key = f"site_monitor:{monitor_id}"
    prev = ctx.memory_get(mem_key) or {}
    previous_state = prev.get("state")

    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "aul-site-monitor/0.1.0"})
    start = time.monotonic()
    status, body_text = None, ""
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            status = resp.status
            body_text = resp.read(512 * 1024).decode("utf-8", errors="replace")
        ok = status == expected_status and (expected_text is None or expected_text in body_text)
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            body_text = e.read(512 * 1024).decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        ok = status == expected_status and (expected_text is None or expected_text in body_text)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        ok = False
        body_text = f"fetch error: {e}"
    response_ms = round((time.monotonic() - start) * 1000.0, 2)

    state = "up" if ok else "down"
    state_changed = previous_state is not None and previous_state != state
    ctx.memory_set(mem_key, {"state": state, "checked_at": _now(), "status": status})
    ctx.log("site_monitor", {"monitor_id": monitor_id, "state": state,
                             "state_changed": state_changed, "status": status})
    ctx.bill(0.001, f"site_monitor {monitor_id}")
    return {
        "ok": ok,
        "status": status,
        "response_ms": response_ms,
        "state": state,
        "state_changed": state_changed,
        "previous_state": previous_state,
        "checked_at": _now(),
    }


def _now():
    return datetime.now(timezone.utc).isoformat()
