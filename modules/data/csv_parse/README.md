# csv_parse (provisional name)

Parse CSV text into typed rows using the stdlib `csv` module, with
delimiter auto-detection.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |

## Permissions

- `data:parse`

## Inputs

- `csv_text` **or** `csv_base64` (exactly one, required)
- `delimiter` — single character; auto-detected from `, ; \t |` when omitted
- `has_header` — default `true`; when `false`, columns are `col_1…col_N`
- `max_rows` — default 10,000; overflow is cut and flagged `truncated`
- `skip_empty` — default `true`

## Honest limits

- All values are returned as strings — no type inference (use `data_transform`
  or your own casting). UTF-8 (with BOM tolerated) only.
- Auto-detection can misfire on single-column or pathological files; pass
  `delimiter` explicitly when you know it.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
