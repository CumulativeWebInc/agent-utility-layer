"""Tests for ocr_image handler. No live network: urlopen is monkeypatched."""

import base64
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handler import AuthMissing, ModuleError, execute  # noqa: E402


class FakeCtx:
    def __init__(self, creds=None):
        self.creds = creds or {}
        self.logs = []

    def auth_get(self, provider):
        if provider not in self.creds:
            raise AuthMissing(f"no credential for '{provider}'")
        return self.creds[provider]

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


# Minimal valid 1x1 PNG (magic + IHDR), content irrelevant — we never hit a real OCR.
PNG_B64 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
).decode("ascii")
JPEG_B64 = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 32).decode("ascii")


class FakeResp:
    def __init__(self, body):
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def _patch(monkeypatch, body):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda req, timeout=None: FakeResp(body)
    )


OCR_OK = json.dumps({
    "IsErroredOnProcessing": False,
    "ParsedResults": [{"ParsedText": "Hello OCR\r\n"}],
})
OCR_ERR = json.dumps({
    "IsErroredOnProcessing": True,
    "ErrorMessage": ["File size too big"],
})


def test_happy_path_ocr_space(monkeypatch):
    _patch(monkeypatch, OCR_OK)
    out = execute({"image_base64": PNG_B64}, FakeCtx({"ocr_space": "k"}))
    assert out["status"] == "ok"
    assert out["provider"] == "ocr_space"
    assert out["text"] == "Hello OCR"
    assert out["confidence"] is None
    assert out["warnings"]  # honest about null confidence


def test_jpeg_accepted(monkeypatch):
    _patch(monkeypatch, OCR_OK)
    out = execute({"image_base64": JPEG_B64, "language": "fra"},
                  FakeCtx({"ocr_space": "k"}))
    assert out["status"] == "ok"


def test_missing_key_raises_auth_missing():
    try:
        execute({"image_base64": PNG_B64}, FakeCtx({}))
        raise AssertionError("expected AuthMissing")
    except AuthMissing as e:
        assert "ocr.space" in str(e).lower() or "api key" in str(e).lower()


def test_empty_key_raises_auth_missing():
    try:
        execute({"image_base64": PNG_B64}, FakeCtx({"ocr_space": ""}))
        raise AssertionError("expected AuthMissing")
    except AuthMissing:
        pass


def test_provider_error_is_module_error(monkeypatch):
    _patch(monkeypatch, OCR_ERR)
    try:
        execute({"image_base64": PNG_B64}, FakeCtx({"ocr_space": "k"}))
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "File size too big" in str(e)


def test_bad_inputs_rejected():
    ctx = FakeCtx({"ocr_space": "k"})
    cases = [
        {"image_base64": "!!!"},
        {"image_base64": base64.b64encode(b"not an image").decode()},
        {"image_base64": ""},
        {"image_base64": PNG_B64, "provider": "nope"},
        {"image_base64": PNG_B64, "language": ""},
        {},
        "nope",
    ]
    for bad in cases:
        try:
            execute(bad, ctx)
            raise AssertionError(f"expected ModuleError for {str(bad)[:40]!r}")
        except ModuleError:
            pass


def test_tesseract_missing_binary_is_module_error(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    try:
        execute({"image_base64": PNG_B64, "provider": "tesseract"}, FakeCtx({}))
        raise AssertionError("expected ModuleError")
    except ModuleError as e:
        assert "tesseract" in str(e).lower()


def test_outputs_match_schema_keys(monkeypatch):
    _patch(monkeypatch, OCR_OK)
    out = execute({"image_base64": PNG_B64}, FakeCtx({"ocr_space": "k"}))
    assert set(out.keys()) == {"status", "provider", "text", "confidence", "warnings"}
