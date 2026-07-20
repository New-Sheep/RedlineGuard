# Dual-store memory (ORM + Chroma)

**Django `Decision` rows** are the system of record (History, Undo, audit links).

**Chroma** (`data/vector_memory`, collection `django_decisions_v2`) is the **retrieval index only** — clause-excerpt similarity for drafting / Memory search.

Unlearn and admin **Reset decisions** clear **both**. Do not swap Chroma mid-demo; a future `DecisionStore` adapter can target pgvector / Oracle 23ai without rewriting the Memory UI.

Chroma is **local and gitignored** — reviewers get an empty index on first clone; use `seed_precedents` or Accept once (see [`13-HANDOFF.md`](13-HANDOFF.md)).
