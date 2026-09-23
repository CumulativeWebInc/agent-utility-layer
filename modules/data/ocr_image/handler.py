"""ocr_image — OCR provider hook + local tesseract path. stdlib only.

No provider key / no binary -> honest error. Text is NEVER fabricated.
"""

import base64
import binascii
import json
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _validate_image(b64: str) -> bytes:
    if not isinstance(b64, str) or not b64.strip():
        raise ModuleError("input 'image_base64' must be a non-empty base64 string")
    try:
        raw = base64.b64decode(b64.strip(), validate=True)
    except (binascii.Error, ValueError) as e:
        raise ModuleError(f"input 'image_base64' is not valid base64: {e}")
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "png"
    elif raw[:2] == b"\xff\xd8":
        kind = "jpeg"
    elif raw[:4] in (b"RIFF",) and raw[8:12] == b"WEBP":
        kind = "webp"
    elif raw[:6] in (b"GIF87a", b"GIF89a"):
        kind = "gif"
    else:
        raise ModuleError(
            "input is not a recognized image (PNG/JPEG/WebP/GIF signatures checked)"
        )
    return raw, kind


def _ocr_space(raw: bytes, kind: str, key: str, lang: str, timeout: float) -> dict:
    data = urllib.parse.urlencode({
        "base64Image": f"data:image/{kind};base64," + base64.b64encode(raw).decode(),
        "language": lang,
        "isOverlayRequired": "false",
        "OCREngine": "2",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.ocr.space/parse/image",
        data=data,
        headers={"apikey": key, "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        raise ModuleError(f"ocr.space request failed: {e}")
    if payload.get("IsErroredOnProcessing"):
        msgs = payload.get("ErrorMessage") or ["unknown OCR.space error"]
        raise ModuleError(f"ocr.space processing error: {'; '.join(map(str, msgs))}")
    results = payload.get("ParsedResults") or []
    if not results:
        raise ModuleError("ocr.space returned no parsed results")
    return {
        "text": (results[0].get("ParsedText") or "").strip(),
        "confidence": None,  # OCR.space free tier returns no reliable confidence
        "warnings": ["ocr.space free tier returns no confidence score; reported as null"],
    }


def _tesseract(raw: bytes, kind: str, lang: str) -> dict:
    exe = shutil.which("tesseract")
    if not exe:
        raise ModuleError(
            "provider 'tesseract' needs a local tesseract-ocr binary, which was not "
            "found on PATH. Install it (e.g. `sudo apt install tesseract-ocr`) or "
            "use provider 'ocr_space' with an API key."
        )
    suffix = {"png": ".png", "jpeg": ".jpg", "webp": ".webp", "gif": ".gif"}[kind]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(raw)
        path = f.name
    try:
        proc = subprocess.run(
            [exe, path, "stdout", "-l", lang],
            capture_output=True, text=True, timeout=120,
        )
    finally:
        try:
            import os
            os.unlink(path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise ModuleError(f"tesseract failed: {proc.stderr.strip()[:500]}")
    return {"text": proc.stdout.strip(), "confidence": None,
            "warnings": ["tesseract stdout path reports no confidence; reported as null"]}


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    provider = inputs.get("provider", "ocr_space")
    if provider not in ("ocr_space", "tesseract"):
        raise ModuleError("input 'provider' must be one of: ocr_space, tesseract")
    raw, kind = _validate_image(inputs.get("image_base64"))
    lang = inputs.get("language", "eng")
    if not isinstance(lang, str) or not lang.strip():
        raise ModuleError("input 'language' must be a non-empty string")
    timeout = inputs.get("timeout_seconds", 60)
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 300:
        raise ModuleError("input 'timeout_seconds' must be a number in (0, 300]")

    if provider == "ocr_space":
        try:
            key = ctx.auth_get("ocr_space")
        except AuthMissing:
            raise AuthMissing(
                "No API key configured for OCR provider 'ocr_space'. Get a free key "
                "at https://ocr.space/ocrapi (free tier available) and store it with "
                "the 'ocr_space' provider."
            )
        if not key or not str(key).strip():
            raise AuthMissing(
                "Empty API key for 'ocr_space'. Get a free key at "
                "https://ocr.space/ocrapi and store it with the 'ocr_space' provider."
            )
        result = _ocr_space(raw, kind, key, lang, timeout)
    else:
        result = _tesseract(raw, kind, lang)

    ctx.log("ocr_image", {"provider": provider, "kind": kind,
                          "chars": len(result["text"])})
    return {
        "status": "ok",
        "provider": provider,
        "text": result["text"],
        "confidence": result["confidence"],
        "warnings": result["warnings"],
    }
