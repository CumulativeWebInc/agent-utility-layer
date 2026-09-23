"""Tests for pdf_extract handler. Fixture PDFs are built inline."""

import base64
import os
import sys
import zlib

from .handler import ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self):
        self.logs = []

    def auth_get(self, provider):
        raise AssertionError("no provider needed")

    def approval_request(self, summary, timeout_seconds=300):
        raise AssertionError("no approval needed")

    def memory_get(self, key):
        return None

    def memory_set(self, key, value):
        pass

    def log(self, event, data):
        self.logs.append((event, data))

    def bill(self, amount_usd, memo):
        pass


def make_pdf(content: bytes, compressed=False, encrypt=False):
    if compressed:
        stream, filt = zlib.compress(content), b"/Filter /FlateDecode"
    else:
        stream, filt = content, b""
    objs = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length %d %s >>\nstream\n%s\nendstream\nendobj\n"
        % (len(stream), filt, stream)
    )
    trailer = b"<< /Root 1 0 R" + (b" /Encrypt 5 0 R" if encrypt else b"") + b" >>"
    return base64.b64encode(
        b"%PDF-1.4\n" + objs + b"trailer\n" + trailer + b"\n%%EOF"
    ).decode("ascii")


def test_happy_path_plain_stream():
    b64 = make_pdf(b"BT /F1 12 Tf 72 720 Td (Hello World) Tj ET")
    out = execute({"pdf_base64": b64}, FakeCtx())
    assert out["status"] == "ok"
    assert out["page_count"] == 1
    assert "Hello World" in out["text"]
    assert out["char_count"] == len(out["text"])
    assert out["truncated"] is False


def test_flate_compressed_stream():
    content = b"BT (Compressed Text) Tj ET"
    out = execute({"pdf_base64": make_pdf(content, compressed=True)}, FakeCtx())
    assert "Compressed Text" in out["text"]


def test_tj_array_and_hex_strings():
    content = b"BT [(Hel) -20 (lo)] TJ ET BT <576F726C64> Tj ET"
    out = execute({"pdf_base64": make_pdf(content)}, FakeCtx())
    assert "Hello" in out["text"]
    assert "World" in out["text"]


def test_escaped_parens_and_octal():
    content = rb"BT (a\(b\) \101) Tj ET"
    out = execute({"pdf_base64": make_pdf(content)}, FakeCtx())
    assert "a(b)" in out["text"]
    assert "A" in out["text"]  # \101 octal


def test_empty_text_pdf_warns():
    out = execute({"pdf_base64": make_pdf(b"BT ET")}, FakeCtx())
    assert out["status"] == "ok"
    assert out["text"] == ""
    assert any("no extractable text" in w for w in out["warnings"])


def test_truncation_flag():
    b64 = make_pdf(b"BT (" + b"x" * 500 + b") Tj ET")
    out = execute({"pdf_base64": b64, "max_chars": 10}, FakeCtx())
    assert out["truncated"] is True
    assert out["char_count"] == 10


def test_encrypted_pdf_rejected():
    try:
        execute({"pdf_base64": make_pdf(b"BT (x) Tj ET", encrypt=True)}, FakeCtx())
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "encrypt" in str(e).lower()


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    good = make_pdf(b"BT (x) Tj ET")
    cases = [
        {"pdf_base64": "!!!not-base64!!!"},
        {"pdf_base64": base64.b64encode(b"definitely not a pdf").decode()},
        {"pdf_base64": ""},
        {},
        {"pdf_base64": good, "max_chars": 0},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:40]!r}")
        except ModuleError:
            pass


def test_outputs_match_schema_keys():
    out = execute({"pdf_base64": make_pdf(b"BT (k) Tj ET")}, FakeCtx())
    assert set(out.keys()) == {
        "status", "page_count", "text", "char_count", "truncated", "warnings"
    }
