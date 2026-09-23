# template_demo — reference module (provisional name)

One-line purpose: proves CONTRACT.md end to end — auth, approval, billing,
input validation, and the demo/real split — with a SIMULATED provider.

- **Pricing:** setup $1.00 · execution $0.001 · approval $0.01 (only when
  `destructive=true` in real mode).
- **Permissions required:** `template:demo`
- **Provider setup:** real mode needs a credential named `template_provider`
  via `ctx.auth_get` (env `AUL_CRED_TEMPLATE_PROVIDER` or the credentials
  file). Demo mode needs nothing.
- **Honest limits:** the provider is SIMULATED in every mode. Real mode
  exercises the real credential and approval plumbing, but the "echo" is still
  produced locally — this module never sends, spends, or touches a real
  provider. It exists so module crews can copy a working pattern, not to do
  real work.
- **Kill rule:** reference module — exempt from the 60-day kill rule; it is
  retired only if the contract itself is replaced.

© 2026 Cumulative Web Inc
