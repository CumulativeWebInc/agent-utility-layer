# dns_lookup (provisional name)

Resolve a hostname via stdlib socket (A/AAAA/CNAME only in v1).

## Pricing
- Setup: $1.00 · Per execution: $0.001 · Human-approval push: $0.01
  (venture defaults; no deviation for this module)

## Permissions required
- `net:dns`

## Provider setup
No provider needed; uses the host resolver via socket.getaddrinfo.

## Approval
None required.

## Honest limits
- Real resolution via the OS resolver — honors the machine's DNS config, no custom nameservers.
- MX/TXT/SRV and friends are NOT supported with stdlib alone (needs dnspython) — requesting them raises ModuleError, honestly, instead of faking an answer.

## Kill rule
No real usage within 60 days of listing -> kill the module or merge it into a sibling module.

© 2026 Cumulative Web Inc
