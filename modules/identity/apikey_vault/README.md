# apikey_vault (provisional name)

Encrypted-at-rest API key vault: store, retrieve, rotate, revoke, list (values never listed).

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `vault:write`
- `vault:read`

## Provider setup
Master key from ctx.auth_get('vault_master'). Vault blobs live in ctx.memory (spine-persisted). Never pass key_value to 'list'; list returns names + last4 only.

## Approval
store/rotate/revoke require ctx.approval_request. retrieve/list do not.

## Honest limits
- v1 $0 construction: PBKDF2-HMAC-SHA256 (200k) -> HMAC-SHA256-CTR stream cipher + HMAC authentication, all stdlib. Honest caveat: key management is the operator's job — a KMS/HSM replaces vault_master in production; this module documents the seam but does not fake one.
- Wrong master key -> decryption failure (ModuleError), never a silent wrong value.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
