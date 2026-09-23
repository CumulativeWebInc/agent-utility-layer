# inventory_check (provisional name)

One-line purpose: track inventory SKUs with on-hand quantities, reservations,
and reorder points — adjust stock, reserve/release units, and report
low-stock items.

## Pricing

- Setup: $1.00
- Per execution: $0.001
- Human-approval push: n/a (internal store only)

## Permissions required

- `inventory:write`

## Provider setup

No warehouse/ERP provider integrated. Stock lives in the spine's scoped
memory (`ctx.memory`, key `aul:inventory_v1`).

## Honest limits

- **Real:** guarded stock arithmetic — adjustments can never drive on-hand
  negative or below reserved units; reservations can never exceed available
  stock; releases can never exceed reserved stock. `available = on_hand -
  reserved` is computed, never guessed.
- **Not real / stubbed:** stock numbers reflect only what was recorded
  through this module — it never infers, estimates, or fabricates counts,
  and there is no live warehouse feed. Demo runs against an in-memory
  FakeCtx, labeled "DEMO — simulated providers".

## Kill rule

No real usage within 60 days of listing → kill the module or merge it into a
sibling business module.

© 2026 Cumulative Web Inc
