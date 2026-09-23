# pdf_extract (provisional name)

Extract plain text from a PDF using stdlib only — content-stream parsing
(`Tj`/`TJ` operators), no external libraries, no OCR.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |

## Permissions

- `data:parse`

## Inputs

- `pdf_base64` (required) — the PDF file, base64-encoded
- `max_chars` — default 200,000; longer text is cut and flagged `truncated`

## Honest limits — read before relying on output

- **Real** for text-based PDFs with uncompressed or FlateDecode-compressed
  content streams. **Not** for: scanned-image PDFs (use `ocr_image`),
  encrypted/password-protected PDFs (rejected with `ModuleError`),
  PDFs using custom glyph encodings (bytes decoded best-effort as latin-1),
  or non-FlateDecode filters (LZW, etc.).
- Text order follows content-stream order — usually reading order, but not
  guaranteed. Columns, tables, and layout are NOT reconstructed.
- `page_count` is counted from `/Type /Page` objects; an absent or unusual
  page tree may undercount. Empty results carry a `warnings` entry explaining
  why instead of silently returning nothing.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
