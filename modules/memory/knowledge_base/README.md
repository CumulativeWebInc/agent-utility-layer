# knowledge_base (provisional)

Document store with word-window chunking and lexical (TF-IDF) retrieval over chunks.

## Pricing
- Setup: $1.00 USD
- Per execution: $0.0010 USD

## Permissions required
- `memory:knowledge_base`

## Provider setup
sqlite3 via stdlib; chunking + TF-IDF scoring in pure Python.

## Honest limits
Real chunking and real retrieval, but retrieval is LEXICAL (TF-IDF over terms), not semantic. For semantic retrieval, embed chunks and use vector_search. Chunking is word-window based, not sentence-aware.

## Kill rule
no real usage in 60 days -> kill or merge

© 2026 Cumulative Web Inc
