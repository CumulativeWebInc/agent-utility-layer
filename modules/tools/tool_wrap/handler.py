"""tool_wrap — POST /v1/tools/wrap: turn a URL / OpenAPI spec / HTML page into an
OpenAI-style function spec for LLMs.

Real logic, $0, stdlib only (urllib + html.parser):
  1. Fetch target_url (10s timeout).
  2. If the body is an OpenAPI/Swagger document -> function spec from the
     matching operation (method-aware; falls back to the first path).
  3. Else if the body is HTML -> one function spec per <form> (inputs become
     parameters).
  4. Else -> heuristic spec derived from the URL path.

Never fabricates: a fetch failure raises ModuleError; the auth_token is
validated (when auth_type demands one) but NEVER stored, logged, or returned.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

EXEC_PRICE_USD = 1.00  # deviation from $0.001 default: the concept doc prices
# each wrap at $1.00; the wrap IS the value-delivering call. See README.
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
AUTH_TYPES = {"none", "bearer", "api_key", "basic", "header"}
FETCH_TIMEOUT_S = 10
MAX_BODY_BYTES = 1_000_000


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _fetch_url(url: str) -> tuple[str, bytes]:
    """Return (content_type, body). Raises ModuleError on any failure."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "agent-utility-layer/0.1.0", "Accept": "*/*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            ctype = resp.headers.get("Content-Type", "")
            return ctype, resp.read(MAX_BODY_BYTES + 1)
    except Exception as e:
        raise ModuleError("could not fetch target_url %r: %s" % (url, e))


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug[:48] or "endpoint"


def _tool_id(url: str, method: str) -> str:
    digest = hashlib.sha256(("%s|%s" % (url, method)).encode()).hexdigest()
    return "tool_" + digest[:8]


class _FormParser(HTMLParser):
    """Extract <form> elements and their named inputs."""

    def __init__(self):
        super().__init__()
        self.forms = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._current = {
                "action": a.get("action", ""),
                "method": (a.get("method") or "get").upper(),
                "id": a.get("id", ""),
                "inputs": [],
            }
        elif self._current is not None and tag in ("input", "select", "textarea"):
            name = a.get("name")
            if name:
                self._current["inputs"].append(
                    {
                        "name": name,
                        "type": a.get("type", "text"),
                        "required": "required" in a,
                    }
                )

    def handle_endtag(self, tag):
        if tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


def _schema_to_properties(schema: dict) -> tuple[dict, list]:
    props, required = {}, []
    if not isinstance(schema, dict):
        return props, required
    for name, subschema in (schema.get("properties") or {}).items():
        if not isinstance(subschema, dict):
            subschema = {}
        prop = {"type": subschema.get("type", "string")}
        if subschema.get("description"):
            prop["description"] = subschema["description"]
        props[name] = prop
    required = [r for r in (schema.get("required") or []) if isinstance(r, str)]
    return props, required


def _spec_from_openapi(doc: dict, method: str) -> dict:
    paths = doc.get("paths") or {}
    chosen = None
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for m, op in item.items():
            if m.upper() == method and isinstance(op, dict):
                chosen = (path, m, op)
                break
        if chosen:
            break
    if not chosen:
        for path, item in paths.items():
            if isinstance(item, dict):
                for m, op in item.items():
                    if isinstance(op, dict):
                        chosen = (path, m, op)
                        break
            if chosen:
                break
    if not chosen:
        raise ModuleError("OpenAPI document contains no usable operations")

    path, m, op = chosen
    name = _slug(op.get("operationId") or ("%s_%s" % (m, path)))
    description = op.get("summary") or op.get("description") or (
        "Calls %s %s" % (m.upper(), path)
    )
    props, required = {}, []
    for p in op.get("parameters") or []:
        if not isinstance(p, dict) or "name" not in p:
            continue
        pname = str(p["name"])
        pschema = p.get("schema") or {}
        prop = {"type": pschema.get("type", "string")}
        if p.get("description"):
            prop["description"] = p["description"]
        props[pname] = prop
        if p.get("required"):
            required.append(pname)
    body = (op.get("requestBody") or {}).get("content") or {}
    for _mt, media in body.items():
        bprops, brequired = _schema_to_properties((media or {}).get("schema") or {})
        props.update(bprops)
        required.extend(r for r in brequired if r not in required)
        break  # first media type only
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": props, "required": required},
        "source": {"kind": "openapi", "path": path, "http_method": m.upper()},
    }


def _spec_from_html(forms: list, url: str, method: str) -> dict:
    specs = []
    for form in forms:
        action = form["action"] or url
        fname = _slug("form_" + (form["id"] or action))
        props, required = {}, []
        for inp in form["inputs"]:
            props[inp["name"]] = {
                "type": "string",
                "description": "HTML %s input '%s'" % (inp["type"], inp["name"]),
            }
            if inp["required"]:
                required.append(inp["name"])
        specs.append(
            {
                "name": fname,
                "description": "Submits the HTML form at %s (%s)"
                % (action, form["method"]),
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
                "source": {"kind": "html_form", "action": action,
                           "http_method": form["method"]},
            }
        )
    if not specs:
        raise ModuleError("no <form> elements found in HTML page")
    return specs[0]


def _spec_heuristic(url: str, method: str) -> dict:
    parts = urllib.parse.urlsplit(url)
    slug = _slug(parts.netloc + " " + parts.path)
    return {
        "name": "%s_%s" % (method.lower(), slug),
        "description": (
            "Generic %s wrapper for %s. The page did not expose an OpenAPI "
            "document or HTML forms, so this spec was derived heuristically "
            "from the URL." % (method, url)
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "source": {"kind": "heuristic_url"},
    }


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. Returns a dict matching outputs_schema."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    target_url = inputs.get("target_url")
    try:
        parts = urllib.parse.urlsplit(target_url or "")
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError()
    except Exception:
        raise ModuleError("target_url must be a valid http(s) URL")

    method = (inputs.get("method") or "GET").upper()
    if method not in METHODS:
        raise ModuleError("invalid method %r; must be one of %s"
                          % (method, sorted(METHODS)))

    auth_type = (inputs.get("auth_type") or "none").lower()
    if auth_type not in AUTH_TYPES:
        raise ModuleError("invalid auth_type %r; must be one of %s"
                          % (auth_type, sorted(AUTH_TYPES)))
    auth_token = inputs.get("auth_token")
    if auth_type != "none" and (not isinstance(auth_token, str) or not auth_token):
        raise ModuleError("auth_token is required when auth_type is %r" % auth_type)
    # auth_token is deliberately NOT persisted, logged, or returned.

    ctype, body = _fetch_url(target_url)
    if len(body) > MAX_BODY_BYTES:
        raise ModuleError("response body exceeds %d bytes" % MAX_BODY_BYTES)

    spec = None
    if "json" in ctype or body.lstrip()[:1] in (b"{", b"["):
        try:
            doc = json.loads(body.decode("utf-8", "replace"))
        except Exception:
            doc = None
        if isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc):
            spec = _spec_from_openapi(doc, method)
    if spec is None and ("html" in ctype or b"<html" in body[:2048].lower()
                         or b"<!doctype" in body[:2048].lower()):
        parser = _FormParser()
        parser.feed(body.decode("utf-8", "replace"))
        if parser.forms:
            spec = _spec_from_html(parser.forms, target_url, method)
    if spec is None:
        spec = _spec_heuristic(target_url, method)

    if auth_type != "none":
        spec["description"] += " Requires %s authentication at call time." % auth_type

    tool_id = _tool_id(target_url, method)
    ctx.log("tool_wrap.wrapped", {"tool_id": tool_id, "source_kind": spec["source"]["kind"]})
    ctx.bill(EXEC_PRICE_USD, "tool_wrap wrap %s" % tool_id)
    return {
        "tool_id": tool_id,
        "openai_function_spec": {
            "name": spec["name"],
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
        "wrap_source": spec["source"]["kind"],
        "auth_type": auth_type,
        "credential_note": (
            "auth_token was accepted for this call only; it is not stored, "
            "logged, or returned. Store credentials in the agent vault and "
            "supply them at execution time." if auth_type != "none"
            else "no authentication configured"
        ),
    }
