# ocr_image (provisional name)

OCR an image via a configured provider. Never fabricates text: without a
provider key (or a local tesseract binary) it raises an honest error.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.005 (above the $0.001 default — OCR provider API cost) |

## Permissions

- `net:egress:ocr`

## Provider setup

- **ocr_space** (default) — free key at https://ocr.space/ocrapi, stored with the
  `ocr_space` provider. Without it, `execute` raises `AuthMissing`.
- **tesseract** — local path, no key: requires the `tesseract-ocr` binary on
  PATH (`sudo apt install tesseract-ocr`). Missing binary → `ModuleError` with
  install instructions.

## Inputs

- `image_base64` (required) — PNG, JPEG, WebP, or GIF
- `provider` — `ocr_space` (default) or `tesseract`
- `language` — default `eng` (tesseract/OCR.space language code)
- `timeout_seconds` — default 60

## Honest limits

- `confidence` is always `null` for now: the OCR.space free tier and the
  tesseract stdout path report no reliable confidence. This is stated in the
  output `warnings`, not silently invented.
- Quality depends entirely on image resolution and the provider; handwriting
  and low-contrast images perform poorly.
- Only PNG/JPEG/WebP/GIF signatures are accepted.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
