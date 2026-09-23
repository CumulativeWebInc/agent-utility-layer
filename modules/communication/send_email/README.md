# send_email (provisional name)

Send an email via the configured SMTP provider.

Pillar: communication · Crew C · version 0.1.0 · provisional: yes
(public brand names come from the screened-names workstream — never invent one)

## Pricing

- Setup: $1.00
- Per execution: $0.001

## Permissions required

- `email:send`

## Provider setup

SMTP via stdlib smtplib; credentials from ctx.auth_get('smtp') as JSON {host, port, username, password, from_addr, use_tls}.

Secrets live in the credential store (ctx.auth_get), never in this repo, never in logs, never in error messages.

## Honest limits

REAL send path via smtplib — requires SMTP credentials + human approval. No credentials -> AuthMissing with setup instructions. Message-ID generated locally per RFC 5322 (make_msgid); delivery confirmation is the SMTP server's 250 OK, never a fabricated receipt. Demo mode uses a fake SMTP transport, clearly labeled.

Every external send / control-plane change requires `ctx.approval_request(...)` first — no exceptions. A denied approval raises ApprovalDenied and nothing is dispatched.

## Kill rule

no real usage in 60 days -> kill or merge into a sibling.

---
© 2026 Cumulative Web Inc
