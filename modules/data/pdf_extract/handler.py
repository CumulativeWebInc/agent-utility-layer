"""pdf_extract — stdlib-only PDF text extraction. No external libs, no OCR.

Honest limits (also in README):
- Parses content-stream text operators (Tj / TJ / ' / ") in uncompressed or
  FlateDecode-compressed streams.
- Does NOT handle: encrypted/password PDFs, scanned-image PDFs (needs OCR),
  exotic encodings (extracted bytes are decoded as latin-1/WinAnsi best-effort),
  or text drawn with custom encodings that remap glyph codes.
- Text order follows content-stream order, which usually matches reading order
  but is not guaranteed. Layout/columns are not reconstructed.
"""

import base64
import binascii
import re
import zlib


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", re.DOTALL)
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_PAGE_RE = re.compile(rb"/Type\s*/Page(?!s)")
_TJ_RE = re.compile(rb"(\((?:\\.|[^()\\])*\))\s*Tj")
_TJ_HEX_RE = re.compile(rb"<([0-9A-Fa-f]+)>\s*Tj")
_TJ_ARR_RE = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
_TJ_ARR_STR = re.compile(rb"\((?:\\.|[^()\\])*\)|<([0-9A-Fa-f]+)>")

_ESCAPES = {
    b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
    b"(": b"(", b")": b")", b"\\": b"\\",
}


def _decode_literal(raw: bytes) -> str:
    # raw includes the surrounding parentheses
    inner = raw[1:-1]
    out = bytearray()
    i = 0
    while i < len(inner):
        c = inner[i:i + 1]
        if c == b"\\" and i + 1 < len(inner):
            nxt = inner[i + 1:i + 2]
            if nxt in _ESCAPES:
                out += _ESCAPES[nxt]
                i += 2
                continue
            if nxt.isdigit():  # octal escape \ddd
                octal = inner[i + 1:i + 4]
                digits = b"".join(
                    octal[j:j + 1] for j in range(len(octal)) if octal[j:j + 1].isdigit()
                )[:3]
                out.append(int(digits, 8) & 0xFF)
                i += 1 + len(digits)
                continue
            out += nxt
            i += 2
            continue
        out += c
        i += 1
    return bytes(out).decode("latin-1")


def _decode_hex(raw_hex: bytes) -> str:
    h = raw_hex.decode("ascii", "replace").replace(" ", "")
    if len(h) % 2:
        h += "0"
    return bytes.fromhex(h).decode("latin-1")


def _extract_from_stream(data: bytes) -> str:
    parts = []
    for m in _TJ_RE.finditer(data):
        parts.append(_decode_literal(m.group(1)))
    for m in _TJ_HEX_RE.finditer(data):
        parts.append(_decode_hex(m.group(1)))
    for m in _TJ_ARR_RE.finditer(data):
        inner = []
        for s in _TJ_ARR_STR.finditer(m.group(1)):
            token = s.group(0)
            if token.startswith(b"("):
                inner.append(_decode_literal(token))
            else:
                inner.append(_decode_hex(s.group(1).encode("ascii")))
        # TJ array numbers are kerning adjustments, not word breaks:
        # concatenate without separator.
        if "".join(inner).strip():
            parts.append("".join(inner))
    return " ".join(p for p in parts if p).strip()


def _get_streams(pdf: bytes):
    streams = []
    for m in _OBJ_RE.finditer(pdf):
        obj = m.group(3)
        sm = _STREAM_RE.search(obj)
        if not sm:
            continue
        raw = sm.group(1)
        if b"/FlateDecode" in obj.split(b"stream")[0]:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                continue
        streams.append(raw)
    return streams


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    b64 = inputs.get("pdf_base64")
    if not isinstance(b64, str) or not b64.strip():
        raise ModuleError("input 'pdf_base64' must be a non-empty base64 string")
    try:
        pdf = base64.b64decode(b64.strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ModuleError(f"input 'pdf_base64' is not valid base64: {e}")
    if not pdf.startswith(b"%PDF"):
        raise ModuleError("input is not a PDF (missing %PDF header)")
    if b"/Encrypt" in pdf:
        raise ModuleError(
            "encrypted/password-protected PDFs are not supported by this module"
        )

    max_chars = inputs.get("max_chars", 200000)
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars <= 0:
        raise ModuleError("input 'max_chars' must be a positive integer")

    page_count = len(_PAGE_RE.findall(pdf))
    warnings = []
    texts = []
    for stream in _get_streams(pdf):
        texts.append(_extract_from_stream(stream))
    text = "\n".join(t for t in texts if t).strip()
    if not text:
        warnings.append(
            "no extractable text found — this PDF may be scanned images "
            "(use ocr_image), use an unsupported encoding, or be empty"
        )

    truncated = len(text) > max_chars
    text = text[:max_chars]
    ctx.log("pdf_extract", {"pages": page_count, "chars": len(text)})
    return {
        "status": "ok",
        "page_count": page_count,
        "text": text,
        "char_count": len(text),
        "truncated": truncated,
        "warnings": warnings,
    }
