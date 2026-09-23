"""doc_parse — real text/structure extraction from txt, md, and docx.

- txt: UTF-8 passthrough (best-effort), sections = paragraphs.
- md: headings parsed into sections (level, title, text); full text preserved.
- docx: stdlib zipfile + XML paragraph extraction (w:p / w:t).
Binary/non-text input is rejected honestly.
"""

import base64
import binascii
import io
import re
import zipfile
import xml.etree.ElementTree as ET


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _looks_binary(raw: bytes) -> bool:
    if b"\x00" in raw:
        return True
    sample = raw[:4096]
    if not sample:
        return False
    ctrl = sum(1 for b in sample if b < 9 or 13 < b < 32)
    return ctrl / len(sample) > 0.05


def _detect_format(raw: bytes, filename: str) -> str:
    if filename:
        lower = filename.lower()
        if lower.endswith(".docx"):
            return "docx"
        if lower.endswith((".md", ".markdown")):
            return "md"
        if lower.endswith(".txt"):
            return "txt"
    if raw.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if "word/document.xml" in z.namelist():
                    return "docx"
        except zipfile.BadZipFile:
            pass
    return "txt"


def _parse_txt(raw: bytes):
    text = raw.decode("utf-8", "replace")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sections = [{"level": 0, "title": f"paragraph {i + 1}", "text": p}
                for i, p in enumerate(paras)]
    return text, sections


def _parse_md(raw: bytes):
    text = raw.decode("utf-8", "replace")
    sections = []
    cur = {"level": 0, "title": "", "lines": []}
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if cur["lines"] or cur["title"]:
                sections.append({"level": cur["level"], "title": cur["title"],
                                 "text": "\n".join(cur["lines"]).strip()})
            cur = {"level": len(m.group(1)), "title": m.group(2).strip(), "lines": []}
        else:
            cur["lines"].append(line)
    if cur["lines"] or cur["title"]:
        sections.append({"level": cur["level"], "title": cur["title"],
                         "text": "\n".join(cur["lines"]).strip()})
    if not sections:
        sections = [{"level": 0, "title": "", "text": text.strip()}]
    return text, sections


def _parse_docx(raw: bytes):
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        xml_bytes = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ModuleError(f"cannot read word/document.xml from .docx: {e}")
    try:
        root = _strip_ns(ET.fromstring(xml_bytes))
    except ET.ParseError as e:
        raise ModuleError(f"word/document.xml is not valid XML: {e}")
    paras = []
    for p in root.iter("p"):
        txt = "".join(node.text or "" for node in p.iter("t"))
        if txt.strip():
            paras.append(txt.strip())
    text = "\n\n".join(paras)
    sections = [{"level": 0, "title": f"paragraph {i + 1}", "text": p}
                for i, p in enumerate(paras)]
    return text, sections


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    b64 = inputs.get("doc_base64")
    if not isinstance(b64, str) or not b64.strip():
        raise ModuleError("input 'doc_base64' must be a non-empty base64 string")
    try:
        raw = base64.b64decode(b64.strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ModuleError(f"input 'doc_base64' is not valid base64: {e}")
    if not raw:
        raise ModuleError("input decoded to empty bytes")
    filename = inputs.get("filename", "")
    if filename is not None and not isinstance(filename, str):
        raise ModuleError("input 'filename' must be a string")
    max_chars = inputs.get("max_chars", 200000)
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars <= 0:
        raise ModuleError("input 'max_chars' must be a positive integer")

    fmt = _detect_format(raw, filename or "")
    if fmt == "txt" and _looks_binary(raw):
        raise ModuleError(
            "input looks like binary data, not a text document "
            "(supported: .txt, .md, .docx)"
        )

    if fmt == "docx":
        text, sections = _parse_docx(raw)
    elif fmt == "md":
        text, sections = _parse_md(raw)
    else:
        text, sections = _parse_txt(raw)

    truncated = len(text) > max_chars
    text = text[:max_chars]
    word_count = len(re.findall(r"\S+", text))
    ctx.log("doc_parse", {"format": fmt, "chars": len(text), "words": word_count})
    return {
        "status": "ok",
        "format": fmt,
        "text": text,
        "sections": sections,
        "word_count": word_count,
        "char_count": len(text),
        "truncated": truncated,
    }
