"""Execution API for the Agent Utility Layer (stdlib only).

Endpoints:
  GET  /v1/health         service status
  GET  /v1/capabilities   registry listing
  POST /v1/execute        {capability, inputs, agent_key, demo?} ->
                          {execution_id, result, billing, demo}

Demo mode: the request sets "demo": true (or ?demo=1). Demo runs only when
the server allows it (env AUL_DEMO=1 or --demo). Demo responses are labeled
"demo": true and modules must use simulated providers there.

The spine NEVER fabricates provider results. Handlers do the work; the spine
authenticates, authorizes, validates inputs, enforces permissions, bills,
and relays. Secrets never appear in logs or errors.

Run:
  AUL_DEMO=1 python3 spine/exec_api.py --port 8741
"""

import importlib.util
import json
import os
import sys
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import KeyStore, key_fingerprint  # noqa: E402
from billing import (  # noqa: E402
    APPROVAL_PRICE_USD,
    record as bill_record,
    total_for,
)
from permissions import enforce, PermissionDenied  # noqa: E402
from registry import load_modules, repo_root, validate_inputs  # noqa: E402

_HANDLER_CACHE: dict[str, tuple[float, object]] = {}


def _load_handler(name: str, path: str):
    mtime = os.path.getmtime(path)
    cached = _HANDLER_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    spec = importlib.util.spec_from_file_location(f"aul_module_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _HANDLER_CACHE[path] = (mtime, module)
    return module


class Ctx:
    """Base execution context. Handlers are duck-typed against this."""

    def __init__(self, agent_id: str, demo: bool, capability: str):
        self.agent_id = agent_id
        self.demo = demo
        self.capability = capability
        self._memory: dict = {}
        self.events: list[dict] = []

    def auth_get(self, provider: str) -> str:
        raise NotImplementedError

    def approval_request(self, summary: str, timeout_seconds: int = 300) -> str:
        raise NotImplementedError

    def memory_get(self, key: str):
        return self._memory.get(key)

    def memory_set(self, key: str, value) -> None:
        self._memory[key] = value

    def log(self, event: str, data: dict) -> None:
        self.events.append({"ts": _now(), "event": event, "data": data or {}})

    def bill(self, amount_usd: float, memo: str) -> dict:
        return bill_record(self.agent_id, self.capability, "exec",
                           amount_usd, "ctx.bill: " + memo)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _creds_store() -> dict:
    """Provider credentials: JSON file outside repo, or AUL_CRED_<NAME> env."""
    path = os.environ.get("AUL_CREDENTIALS_FILE")
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    return {}


class RealCtx(Ctx):
    def auth_get(self, provider: str) -> str:
        store = _creds_store()
        if provider in store:
            return store[provider]
        env_name = "AUL_CRED_" + provider.upper().replace("-", "_")
        if env_name in os.environ:
            return os.environ[env_name]
        # Raise the handler's own AuthMissing when available so contract
        # error types stay consistent.
        raise _module_error(
            "AuthMissing",
            f"No credential configured for provider '{provider}'. "
            f"Set env {env_name} or add '{provider}' to AUL_CREDENTIALS_FILE "
            "(a JSON file outside the repo), then retry."
        )

    def approval_request(self, summary: str, timeout_seconds: int = 300) -> str:
        approval_id = "appr_" + uuid.uuid4().hex[:12]
        bill_record(self.agent_id, self.capability, "approval",
                    APPROVAL_PRICE_USD, f"approval requested: {summary[:120]}")
        _append_pending_approval({
            "id": approval_id, "ts": _now(), "agent_id": self.agent_id,
            "capability": self.capability, "summary": summary,
            "timeout_seconds": timeout_seconds, "status": "pending",
        })
        if os.environ.get("AUL_AUTO_APPROVE") == "1":
            return approval_id
        raise _module_error(
            "ApprovalDenied",
            f"Human approval required (id {approval_id}): {summary}. "
            "Approval is pending — no action was taken. "
            "Set AUL_AUTO_APPROVE=1 only in trusted dev/demo environments."
        )


class DemoCtx(Ctx):
    """Demo context: fake providers, approvals auto-granted and LABELED."""

    def auth_get(self, provider: str) -> str:
        return f"demo-credential-for-{provider}"

    def approval_request(self, summary: str, timeout_seconds: int = 300) -> str:
        bill_record(self.agent_id, self.capability, "approval",
                    APPROVAL_PRICE_USD, "demo auto-approval: " + summary[:120])
        return "appr_demo_" + uuid.uuid4().hex[:8]


def _module_error(class_name: str, message: str) -> Exception:
    """Build ModuleError subclasses without importing handler internals."""
    return type(class_name, (Exception,), {})(message)


def _append_pending_approval(entry: dict) -> None:
    path = os.environ.get(
        "AUL_APPROVALS_FILE",
        os.path.expanduser("~/.config/agent-utility-layer/approvals.jsonl"),
    )
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "AUL-ExecAPI/1.0"

    # set by make_server()
    allow_demo = False
    keys = None
    registry = None

    # -- helpers ---------------------------------------------------------
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, status: int, code: str, message: str, details: dict | None = None):
        self._send_json(status, {"error": {"code": code, "message": message,
                                           "details": details or {}}})

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, fmt, *args):  # quieter access log
        sys.stderr.write("exec_api: " + fmt % args + "\n")

    # -- routes ----------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/v1/health":
            self._send_json(200, {"ok": True, "demo_allowed": self.allow_demo,
                                  "modules_live": len(self.registry.live_modules()),
                                  "ts": _now()})
        elif parsed.path == "/v1/capabilities":
            self._send_json(200, {"capabilities": self.registry.to_listing()})
        elif parsed.path in ("/", "/v1"):
            self._send_json(200, {"service": "agent-utility-layer exec api",
                                  "docs": "POST /v1/execute, GET /v1/capabilities"})
        else:
            self._err(404, "not_found", f"no such route: {parsed.path}")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/v1/execute":
            self._err(404, "not_found", f"no such route: {parsed.path}")
            return
        body = self._read_json()
        if body is None:
            self._err(400, "bad_json", "request body must be JSON")
            return
        self._handle_execute(body, parsed)

    def _handle_execute(self, body: dict, parsed):
        capability_name = body.get("capability")
        inputs = body.get("inputs", {})
        agent_key = body.get("agent_key") or self.headers.get("X-Agent-Key") or ""
        query = urllib.parse.parse_qs(parsed.query)
        demo = bool(body.get("demo")) or query.get("demo", ["0"])[0] == "1"

        if not capability_name or not isinstance(capability_name, str):
            self._err(400, "bad_request", "'capability' (string) is required")
            return
        if demo and not self.allow_demo:
            self._err(403, "demo_disabled",
                       "demo mode is not enabled on this server")
            return

        principal = self.keys.validate(agent_key)
        if principal is None:
            self._err(401, "unauthorized",
                       "invalid or missing agent_key")
            return

        info = self.registry.modules.get(capability_name)
        if info is None:
            self._err(404, "unknown_capability",
                       f"no module named '{capability_name}'")
            return
        if not info.live:
            self._err(409, "module_not_live",
                       f"module '{capability_name}' is not live (state: {info.state})",
                       {"errors": info.errors})
            return
        cap = info.capability

        try:
            enforce(principal, cap.get("permissions", []))
        except PermissionDenied as exc:
            self._err(403, "permission_denied", str(exc))
            return

        input_errors = validate_inputs(cap.get("inputs_schema", {}), inputs or {})
        if input_errors:
            self._err(422, "invalid_inputs", "inputs failed validation",
                       {"errors": input_errors})
            return

        try:
            handler = _load_handler(capability_name, info.handler_path)
        except Exception as exc:  # handler failed to import
            self._err(500, "handler_load_failed",
                       f"handler for '{capability_name}' failed to load: "
                       f"{type(exc).__name__}")
            return
        if not hasattr(handler, "execute"):
            self._err(500, "handler_invalid",
                       f"handler for '{capability_name}' has no execute()")
            return

        ctx = DemoCtx(principal["id"], True, capability_name) if demo \
            else RealCtx(principal["id"], False, capability_name)
        execution_id = "ex_" + uuid.uuid4().hex[:12]
        try:
            result = handler.execute(inputs or {}, ctx)
        except Exception as exc:
            self._map_handler_error(capability_name, exc)
            return
        if not isinstance(result, dict):
            self._err(500, "handler_invalid",
                       f"handler for '{capability_name}' must return a dict")
            return

        price = float(cap.get("price_per_execution_usd", 0.0) or 0.0)
        entry = bill_record(principal["id"], capability_name, "exec", price,
                            f"execution {execution_id}" + (" (demo)" if demo else ""))
        self._send_json(200, {
            "execution_id": execution_id,
            "capability": capability_name,
            "result": result,
            "demo": demo,
            "billing": {
                "amount_usd": entry["amount_usd"],
                "entry_id": entry["id"],
                "agent_total_usd": total_for(principal["id"]),
            },
        })

    def _map_handler_error(self, capability_name: str, exc: Exception):
        name = type(exc).__name__
        message = str(exc)  # handlers must never put secrets in errors (contract)
        if name == "ApprovalDenied":
            self._err(403, "approval_denied", message)
        elif name == "AuthMissing":
            self._err(409, "auth_missing", message)
        elif name == "ModuleError":
            self._err(422, "module_error", message)
        else:
            self._err(500, "handler_failed",
                       f"handler for '{capability_name}' raised {name}: {message[:300]}")


def make_server(port: int, allow_demo: bool, root: str | None = None):
    root = root or repo_root()
    ApiHandler.allow_demo = allow_demo
    ApiHandler.keys = KeyStore()
    ApiHandler.registry = load_modules(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), ApiHandler)
    return server


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description="Agent Utility Layer exec API")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--demo", action="store_true",
                        help="allow demo mode (simulated providers, labeled)")
    args = parser.parse_args(argv)
    allow_demo = args.demo or os.environ.get("AUL_DEMO") == "1"
    server = make_server(args.port, allow_demo)
    actual = server.server_address[1]
    live = len(ApiHandler.registry.live_modules())
    total = len(ApiHandler.registry.modules)
    print(f"exec_api listening on 127.0.0.1:{actual} "
          f"(demo={'on' if allow_demo else 'off'}, modules {live}/{total} live)",
          flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
