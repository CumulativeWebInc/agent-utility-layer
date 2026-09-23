"""web_scrape — real HTTP fetch + HTML text/link extraction. stdlib only."""

import html as html_lib
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


_SKIP_TAGS = {"script", "style", "noscript", "template"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._chunks = []
        self.links = []
        self._cur_href = None
        self._cur_link_text = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            self._cur_href = dict(attrs).get("href")
            self._cur_link_text = []
        if tag in ("br", "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        if tag == "a":
            if self._cur_href:
                text = "".join(self._cur_link_text).strip()
                self.links.append({"href": self._cur_href, "text": text})
            self._cur_href = None
            self._cur_link_text = []

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        else:
            self._chunks.append(data)
            if self._cur_href is not None:
                self._cur_link_text.append(data)

    def text(self):
        raw = "".join(self._chunks)
        lines = [ln.strip() for ln in raw.splitlines()]
        return "\n".join(ln for ln in lines if ln)


def _validate_url(url):
    if not isinstance(url, str) or not url.strip():
        raise ModuleError("input 'url' must be a non-empty string")
    parts = urllib.parse.urlparse(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError(
            f"invalid url '{url}': only absolute http(s) URLs are supported"
        )
    return url.strip()


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    url = _validate_url(inputs.get("url"))
    mode = inputs.get("extract_mode", "text")
    if mode not in ("text", "html", "links"):
        raise ModuleError("input 'extract_mode' must be one of: text, html, links")
    timeout = inputs.get("timeout_seconds", 20)
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 120:
        raise ModuleError("input 'timeout_seconds' must be a number in (0, 120]")
    max_bytes = inputs.get("max_bytes", 1024 * 1024)
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ModuleError("input 'max_bytes' must be a positive integer")
    ua = inputs.get("user_agent", "CWI-AgentUtilityLayer/1.0")

    req = urllib.request.Request(url, headers={"User-Agent": str(ua)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        raise ModuleError(f"fetch failed for '{url}': {e}")

    truncated = len(raw) > max_bytes
    raw = raw[:max_bytes]
    try:
        body = raw.decode("utf-8")
    except UnicodeDecodeError:
        body = raw.decode("utf-8", "replace")

    parser = _Extractor()
    try:
        parser.feed(body)
    except Exception as e:  # HTMLParser is lenient; guard anyway
        raise ModuleError(f"html parse failed: {e}")
    title = html_lib.unescape(parser.title.strip())
    text = parser.text() if mode == "text" else ""
    links = parser.links if mode in ("links", "text") else []

    ctx.log("web_scrape", {"url": url, "bytes": len(raw), "links": len(links)})
    return {
        "status": "ok",
        "url": url,
        "title": title,
        "text": text,
        "char_count": len(text),
        "links": links,
        "link_count": len(links),
        "fetched_bytes": len(raw),
        "truncated": truncated,
    }
