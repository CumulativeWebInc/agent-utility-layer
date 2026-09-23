# doc_parse (provisional name)

Extract text and structure from documents: plain text, Markdown sections, or
`.docx` paragraphs — stdlib only.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |

## Permissions

- `data:parse`

## Inputs

- `doc_base64` (required) — the document bytes, base64-encoded
- `filename` — optional hint (`.txt`, `.md`, `.docx`); without it, format is
  detected from content (ZIP + `word/document.xml` → docx, else text)
- `max_chars` — default 200,000; longer text is cut and flagged `truncated`

## Honest limits

- **txt:** UTF-8 passthrough with undecodable bytes replaced (`�`), sections =
  paragraphs. Binary-looking input is rejected, not guessed.
- **md:** headings (`#`…`######`) become sections; other Markdown syntax
  (tables, links, code fences) is kept as literal text, not rendered.
- **docx:** paragraph text (`w:p`/`w:t`) only — tables, headers/footers,
  footnotes, comments, embedded images, and styles are NOT extracted.
  Tracked-change deletions still present in the XML will appear.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
