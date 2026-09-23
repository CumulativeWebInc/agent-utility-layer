"""browser_action — v1 honest stand-in for browser automation.

action=submit_form: fetch the page, parse plain-HTML forms, POST the chosen
form's fields. No JavaScript, no sessions beyond one request, no CAPTCHA.
Always requires ctx.approval_request.
"""
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


class _FormParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.forms = []
        self._cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._cur = {"action": urllib.parse.urljoin(self.base, a.get("action", "")),
                         "method": a.get("method", "get").upper(),
                         "name": a.get("name", ""),
                         "fields": []}
            self.forms.append(self._cur)
        elif tag in ("input", "select", "textarea") and self._cur is not None:
            f = {"name": a.get("name", ""), "type": a.get("type", "text"),
                 "value": a.get("value", "")}
            if tag == "select":
                f["type"] = "select"
            if tag == "textarea":
                f["type"] = "textarea"
            self._cur["fields"].append(f)

    def handle_endtag(self, tag):
        if tag == "form":
            self._cur = None


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action != "submit_form":
        raise ModuleError("action must be 'submit_form' in v1")
    url = inputs.get("url")
    if not url or not isinstance(url, str):
        raise ModuleError("inputs.url is required (string)")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("url must be an absolute http(s) URL")
    fields = inputs.get("fields")
    if not isinstance(fields, dict):
        raise ModuleError("inputs.fields is required (object)")
    form_sel = inputs.get("form") or {}
    if not isinstance(form_sel, dict):
        raise ModuleError("inputs.form must be an object")
    timeout = inputs.get("timeout_seconds", 15)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
        raise ModuleError("timeout_seconds must be a number in (0, 120]")

    ctx.approval_request(f"browser_action: submit_form on {url} fields={sorted(fields)}")

    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "aul-browser-action/0.1.0"}),
                timeout=float(timeout)) as resp:
            html = resp.read(1_048_576 + 1).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ModuleError(f"page fetch failed: {e}")
    except urllib.error.HTTPError as e:
        raise ModuleError(f"page fetch failed: HTTP {e.code}")

    parser = _FormParser(url)
    parser.feed(html)
    form = _pick_form(parser.forms, form_sel)
    names = {f["name"] for f in form["fields"] if f["name"]}
    unknown = [k for k in fields if k not in names]
    if unknown:
        raise ModuleError(f"unknown form fields: {unknown} (available: {sorted(names)})")

    body = {}
    for f in form["fields"]:
        if f["name"] and f["name"] in fields:
            body[f["name"]] = fields[f["name"]]
        elif f["name"] and f["type"] not in ("submit", "button") and f["value"]:
            body[f["name"]] = f["value"]  # carry hidden defaults
    encoded = urllib.parse.urlencode(body).encode("utf-8")
    target = form["action"] or url
    method = form["method"] if form["method"] in ("GET", "POST") else "POST"
    req = urllib.request.Request(target, data=encoded if method == "POST" else None,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 method=method)
    if method == "GET":
        target = target + ("&" if "?" in target else "?") + urllib.parse.urlencode(body)
        req = urllib.request.Request(target, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            status = resp.status
            excerpt = resp.read(8192).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        excerpt = e.read(8192).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ModuleError(f"form submit failed: {e}")

    ctx.log("browser_action", {"action": action, "url": url, "submitted_to": target, "status": status})
    ctx.bill(0.001, f"browser_action submit_form {url}")
    return {
        "status": status,
        "submitted_to": target,
        "response_body_excerpt": excerpt,
        "fields_sent": sorted(body.keys()),
    }


def _pick_form(forms, sel):
    if not forms:
        raise ModuleError("no HTML forms found on the page")
    if "index" in sel:
        idx = sel["index"]
        if not isinstance(idx, int) or not (0 <= idx < len(forms)):
            raise ModuleError(f"form.index out of range (0..{len(forms)-1})")
        return forms[idx]
    if "name" in sel:
        for f in forms:
            if f["name"] == sel["name"]:
                return f
        raise ModuleError(f"no form named '{sel['name']}'")
    return forms[0]
