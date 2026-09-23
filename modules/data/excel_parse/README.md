# excel_parse (provisional name)

Parse `.xlsx` workbooks into rows using stdlib `zipfile` + `xml.etree` —
no external libraries.

## Pricing

| Item | Price |
|---|---|
| Setup | $1.00 |
| Per execution | $0.001 |

## Permissions

- `data:parse`

## Inputs

- `file_base64` (required) — the `.xlsx` file, base64-encoded
- `sheet` — sheet name; defaults to the first sheet
- `header_row` — default `true`; when `false`, columns are `col_1…col_N`
- `max_rows` — default 10,000; overflow is cut and flagged `truncated`

## Honest limits

- **Real** for `.xlsx` (OOXML): shared strings, inline strings, numbers,
  booleans, and cached formula-string values. Dates come through as raw
  serial numbers — no date conversion is performed.
- **Not supported:** legacy `.xls` (BIFF binary — rejected with `ModuleError`),
  formula evaluation, charts, macros, images, pivot tables. Formula cells
  report their last cached value only.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a sibling.

© 2026 Cumulative Web Inc
