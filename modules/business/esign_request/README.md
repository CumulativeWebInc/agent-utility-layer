# esign_request (provisional name)

One-line purpose: create an e-signature request record (document reference,
signer list, per-signer pending status, expiry) behind a human approval —
signatures complete only in the human loop, never fabricated.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: $0.01 (every `create` — invitations are an external
  send, so the approval is mandatory)

## Permissions required

- `esign:request`

## Provider setup

No e-sign provider integrated (no DocuSign/HelloSign). Requests live in the
spine's scoped memory (`ctx.memory`, key `aul:esign_requests_v1`). The
`approval_id` returned on create is the spine's approval hook receipt.

## Honest limits

- **Real:** approval-gated creation, validated signer emails, unique
  per-signer tokens, expiry timestamps, cancellation.
- **Not real / stubbed:** the module NEVER reports a signature as complete.
  Status stays `pending_signature` until the request is cancelled (or a
  future provider integration records a real signature event). There is no
  code path that marks a signer "signed" — fabricating one would violate the
  honesty law. Demo runs against an in-memory FakeCtx, labeled
  "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
