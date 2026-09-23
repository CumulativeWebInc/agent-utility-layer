"""page_interact — fetch a page and extract structured content with stdlib HTML parsing.

Static HTML only: no JavaScript execution. Forms are extracted but never submitted.
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

EXTRACTABLE = {"title", "headings", "links", "forms", "meta", "text"}
_VOID = {"input", "br", "hr", "img", "meta", "link", "area", "base", "col",
         "embed", "source", "track", "wbr"}


class _PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.title = ""
        self._in_title = False
        self.headings = []
        self._cur_heading = None
        self.links = []
        self.forms = []
        self._cur_form = None
        self.meta = {}
        self._text_parts = []
        self._skip = 0  # inside script/style

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._cur_heading = {"level": tag, "text": ""}
        elif tag == "a" and a.get("href"):
            self.links.append({"text": "", "href": urllib.parse.urljoin(self.base, a["href"])})
        elif tag == "meta":
            name = a.get("name") or a.get("property")
            if name and "content" in a:
                self.meta[name] = a["content"]
        elif tag == "form":
            self._cur_form = {"action": urllib.parse.urljoin(self.base, a.get("action", "")),
                              "method": a.get("method", "get").upper(),
                              "name": a.get("name", ""),
                              "fields": []}
            self.forms.append(self._cur_form)
        elif tag in ("input", "select", "textarea") and self._cur_form is not None:
            field = {"tag": tag, "name": a.get("name", ""), "type": a.get("type", "text")}
            if "value" in a:
                field["default"] = a["value"]
            self._cur_form["fields"].append(field)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._cur_heading:
            t = self._cur_heading["text"].strip()
            if t:
                self.headings.append({"level": self._cur_heading["level"], "text": t})
            self._cur_heading = None
        elif tag == "form":
            self._cur_form = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        if self._cur_heading is not None:
            self._cur_heading["text"] += data
        if self.links and not self.links[-1]["text"]:
            self.links[-1]["text"] = data.strip()
        if data.strip():
            self._text_parts.append(data.strip())


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    url = inputs.get("url")
    if not url or not isinstance(url, str):
        raise ModuleError("inputs.url is required (string)")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("url must be an absolute http(s) URL")
    extract = inputs.get("extract", ["title", "headings", "links"])
    if not isinstance(extract, list) or not extract or not set(extract) <= EXTRACTABLE:
        raise ModuleError(f"extract must be a non-empty list from {sorted(EXTRACTABLE)}")
    max_bytes = inputs.get("max_bytes", 524288)
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ModuleError("max_bytes must be a positive integer")
    timeout = inputs.get("timeout_seconds", 10)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
        raise ModuleError("timeout_seconds must be a number in (0, 120]")

    req = urllib.request.Request(url, headers={"User-Agent": "aul-page-interact/0.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise ModuleError(f"page fetch failed: HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ModuleError(f"page fetch failed: {e}")
    if "html" not in content_type.lower():
        raise ModuleError(f"not an HTML page (Content-Type: {content_type or 'unknown'})")

    parser = _PageParser(url)
    parser.feed(raw.decode("utf-8", errors="replace"))

    out = {"url": url, "title": parser.title.strip(), "headings": parser.headings,
           "links": parser.links, "forms": parser.forms, "meta": parser.meta,
           "text_excerpt": " ".join(parser._text_parts)[:2000]}
    ctx.log("page_interact", {"url": url, "extract": extract,
                              "forms_found": len(parser.forms), "links_found": len(parser.links)})
    ctx.bill(0.001, f"page_interact {url}")
    keep = set(extract) | {"url"}
    if "text" in extract:
        keep.add("text_excerpt")  # extract token "text" -> output key "text_excerpt"
    return {k: v for k, v in out.items() if k in keep}
