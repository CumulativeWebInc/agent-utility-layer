# vector_search (provisional)

Vector similarity store: upsert embeddings, run real cosine-similarity top-k search.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:vector_search`

## Provider setup
sqlite3 via stdlib; embeddings stored as JSON, cosine similarity computed in Python.

## Honest limits
HONEST: no embedding model is bundled — the caller MUST supply embedding vectors. $0 options: sentence-transformers, fastembed, or any embedding API (vectors passed in). Search is exact brute-force cosine over stored vectors; no ANN index (fine to ~100k vectors).

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
