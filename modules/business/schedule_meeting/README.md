# schedule_meeting (provisional name)

One-line purpose: generate a real RFC 5545 `.ics` calendar file for a meeting
— it builds the file; it does not send invitations.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a — no external send, no approval needed

## Permissions required

- `calendar:write`

## Provider setup

None. Pure generator: parses ISO-8601 times, converts to UTC, escapes text
per RFC 5545, folds long lines at 75 octets, emits `BEGIN:VCALENDAR` …
`END:VCALENDAR`. Import the returned `.ics` in Google/Apple/Outlook Calendar,
or send it via `send_email` (which requires a human approval).

## Honest limits

- **Real:** deterministic, standards-compliant `.ics` text — verified in tests
  (UTC conversion, escaping, folding, UID uniqueness).
- **Not real / stubbed:** this module contacts no calendar provider and
  sends no invitations. A "booking" it did not send would be fabrication —
  this module never claims one. Demo output is the real `.ics` text, not a
  simulated provider.

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
