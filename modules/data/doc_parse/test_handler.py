"""Tests for doc_parse handler. Fixtures built inline."""

import base64
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handler import ModuleError, execute  # noqa: E402


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


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def make_docx(paras):
    buf = io.BytesIO()
    p_xml = "".join(
        '<w:p><w:r><w:t xml:space="preserve">' + p + "</w:t></w:r></w:p>"
        for p in paras
    )
    doc = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{p_xml}</w:body></w:document>")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def test_txt_passthrough():
    out = execute({"doc_base64": b64(b"Hello world\n\nSecond para"),
                   "filename": "note.txt"}, FakeCtx())
    assert out["format"] == "txt"
    assert out["word_count"] == 4
    assert len(out["sections"]) == 2
    assert out["sections"][0]["text"] == "Hello world"


def test_md_headings_to_sections():
    md = b"# Title\n\nintro text\n\n## Sub\n\nbody here\n"
    out = execute({"doc_base64": b64(md), "filename": "doc.md"}, FakeCtx())
    assert out["format"] == "md"
    titles = [s["title"] for s in out["sections"]]
    assert titles == ["Title", "Sub"]
    assert out["sections"][0]["level"] == 1
    assert out["sections"][1]["level"] == 2
    assert "intro text" in out["sections"][0]["text"]


def test_docx_paragraph_extraction():
    raw = make_docx(["First para", "Second para with more words"])
    out = execute({"doc_base64": b64(raw), "filename": "report.docx"}, FakeCtx())
    assert out["format"] == "docx"
    assert "First para" in out["text"]
    assert "Second para with more words" in out["text"]
    assert out["word_count"] == 7
    assert len(out["sections"]) == 2


def test_docx_detected_by_magic_without_filename():
    raw = make_docx(["Magic detect"])
    out = execute({"doc_base64": b64(raw)}, FakeCtx())
    assert out["format"] == "docx"
    assert "Magic detect" in out["text"]


def test_binary_rejected():
    try:
        execute({"doc_base64": b64(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)},
                FakeCtx())
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "binary" in str(e).lower()


def test_bad_inputs_rejected():
    ctx = FakeCtx()
    cases = [
        {"doc_base64": "!!!"},
        {"doc_base64": b64(b"")},
        {},
        {"doc_base64": b64(b"hi"), "filename": 5},
        {"doc_base64": b64(b"hi"), "max_chars": 0},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:40]!r}")
        except ModuleError:
            pass


def test_truncation_and_counts():
    out = execute({"doc_base64": b64(b"a " * 500), "max_chars": 10}, FakeCtx())
    assert out["truncated"] is True
    assert out["char_count"] == 10


def test_outputs_match_schema_keys():
    out = execute({"doc_base64": b64(b"hi there")}, FakeCtx())
    assert set(out.keys()) == {
        "status", "format", "text", "sections",
        "word_count", "char_count", "truncated",
    }
