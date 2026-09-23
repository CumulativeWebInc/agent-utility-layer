"""Shared helpers for Crew C (communication + human) capability modules.

Stdlib only. Handlers import this module via a small sys.path shim so the
module loads whether the spine imports it as part of the agent-utility-layer
package or pytest loads it standalone.
"""
import json
import re
import ssl
import uuid


class ModuleError(Exception):
    """Raised for invalid inputs or provider failures."""


class AuthMissing(ModuleError):
    """Raised when a required provider credential is not configured."""


class ApprovalDenied(ModuleError):
    """Raised when the human denies an approval request."""


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-().]{6,}$")


def is_email(value):
    return isinstance(value, str) and bool(_EMAIL_RE.match(value.strip()))


def is_phone(value):
    return isinstance(value, str) and bool(_PHONE_RE.match(value.strip()))


def validate_inputs(inputs, schema):
    """Minimal JSON-schema-ish validation. Raises ModuleError on any problem."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        val = inputs.get(req)
        if val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, list) and not val):
            raise ModuleError("missing required input: %s" % req)
    for key, val in inputs.items():
        if key not in props:
            raise ModuleError("unknown input: %s" % key)
        spec = props[key]
        _check_type(key, val, spec.get("type"))
        if spec.get("format") == "email" and isinstance(val, str) and not is_email(val):
            raise ModuleError("invalid email for input '%s': %r" % (key, val))
        if spec.get("format") == "phone" and isinstance(val, str) and not is_phone(val):
            raise ModuleError("invalid phone number for input '%s': %r" % (key, val))
        if "enum" in spec and val not in spec["enum"]:
            raise ModuleError("invalid value for input '%s': %r (must be one of %s)"
                              % (key, val, spec["enum"]))
        if spec.get("minLength") and isinstance(val, str) and len(val) < spec["minLength"]:
            raise ModuleError("input '%s' is shorter than minLength %d" % (key, spec["minLength"]))
    return True


def _check_type(key, val, type_name):
    if not type_name:
        return
    checks = {
        "string": isinstance(val, str),
        "integer": isinstance(val, int) and not isinstance(val, bool),
        "number": isinstance(val, (int, float)) and not isinstance(val, bool),
        "boolean": isinstance(val, bool),
        "array": isinstance(val, list),
        "object": isinstance(val, dict),
    }
    if not checks.get(type_name, True):
        raise ModuleError("input '%s' must be of type %s" % (key, type_name))


def json_cred(ctx, name, setup_hint):
    """Fetch a provider credential via ctx and parse it as a JSON object.

    Raises AuthMissing (with setup instructions) when unconfigured.
    """
    try:
        raw = ctx.auth_get(name)
    except AuthMissing:
        raise AuthMissing(
            "Provider credential '%s' is not configured. %s" % (name, setup_hint))
    except Exception as exc:  # defensive: any ctx failure becomes AuthMissing
        raise AuthMissing("Could not retrieve credential '%s': %s. %s" % (name, exc, setup_hint))
    try:
        cred = json.loads(raw)
    except Exception:
        raise ModuleError("Credential '%s' must be a JSON object. %s" % (name, setup_hint))
    if not isinstance(cred, dict):
        raise ModuleError("Credential '%s' must be a JSON object. %s" % (name, setup_hint))
    return cred


def new_id(prefix):
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


def smtp_send(cred, msg):
    """Send an email.message.EmailMessage via SMTP using a credential dict.

    Credential shape: {"host", "port"?, "username", "password", "from_addr",
    "use_tls"?}. Secrets are never logged or included in errors.
    """
    import smtplib
    for field in ("host", "username", "password", "from_addr"):
        if not cred.get(field):
            raise ModuleError("smtp credential is missing required field '%s'" % field)
    host = cred["host"]
    port = int(cred.get("port", 587))
    context = ssl.create_default_context()
    try:
        if cred.get("use_tls", True):
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.starttls(context=context)
                server.login(cred["username"], cred["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
                server.login(cred["username"], cred["password"])
                server.send_message(msg)
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        raise ModuleError("smtp send failed: %s: %s" % (type(exc).__name__, exc))


def ics_escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


# ---------------------------------------------------------------------------
# Test doubles (used by test_handler.py files; never in production paths)
# ---------------------------------------------------------------------------

class FakeCtx:
    """Duck-typed stand-in for the spine ctx used in unit tests."""

    def __init__(self, auth=None, approve=True):
        self._auth = dict(auth or {})
        self._approve = approve
        self.memory = {}
        self.logs = []
        self.bills = []
        self.approvals = []

    def auth_get(self, provider):
        if provider not in self._auth:
            raise AuthMissing("provider '%s' not configured" % provider)
        return self._auth[provider]

    def approval_request(self, summary, timeout_seconds=300):
        self.approvals.append(summary)
        if not self._approve:
            raise ApprovalDenied("human denied approval: %s" % summary)
        return "appr_%s" % uuid.uuid4().hex[:12]

    def memory_get(self, key):
        return self.memory.get(key)

    def memory_set(self, key, value):
        self.memory[key] = value

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        self.bills.append((amount_usd, memo))


class FakeSMTP:
    """Test double for smtplib.SMTP / smtplib.SMTP_SSL."""

    sent = []  # class-level record; tests reset it

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, context=None):
        pass

    def login(self, username, password):
        self._user = username

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


class FakeHTTPResponse:
    """Test double for urllib responses (context manager with .read())."""

    def __init__(self, payload, code=200):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
        self._payload = payload.encode("utf-8") if isinstance(payload, str) else payload
        self._code = code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._payload

    def getcode(self):
        return self._code


def fake_urlopen_factory(payload, code=200, record=None):
    def _fake(request, timeout=None):
        if record is not None:
            record.append(request)
        return FakeHTTPResponse(payload, code)
    return _fake
