# send_calendar_invite (provisional name)

Build an iCalendar invite and email it to attendees via SMTP.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `calendar:invite`
- `email:send`

## Provider setup

ICS built by hand (no deps), delivered as text/calendar attachment via SMTP (ctx.auth_get('smtp')). ISO-8601 start/end; naive datetimes treated as UTC.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL SMTP send — requires credentials + human approval. Not a calendar-API integration (no Google/Outlook API); delivery = email with .ics. No credentials -> AuthMissing. Demo mode uses a fake SMTP transport, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge.

---
© 2026 Cumulative Web Inc
