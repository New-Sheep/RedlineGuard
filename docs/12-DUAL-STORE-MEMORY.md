# Dual-store memory (ORM + Chroma)

**Purpose:** One invariant for decision memory. Flows: [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md). Architecture: [`16-CURRENT-ARCHITECTURE.md`](16-CURRENT-ARCHITECTURE.md).

| Store | Role |
|-------|------|
| Django `Decision` rows | System of record (History, Undo, audit links) |
| Chroma (`data/vector_memory`, `django_decisions_v2`) | Retrieval index for clause-excerpt similarity (drafting / Memory search) |

Unlearn and admin **Reset decisions** clear both stores. Chroma is local and gitignored; first clone starts empty until `seed_precedents` or an Accept (see [`13-HANDOFF.md`](13-HANDOFF.md)).

A future `DecisionStore` adapter can target pgvector / Oracle 23ai while keeping the Memory UI.
