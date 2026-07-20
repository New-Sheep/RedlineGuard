# MVP audit checkpoint — RedlineGuard

| | |
|---|---|
| **Document type** | Retrospective + secure LLM roadmap |
| **Date** | 2026-07-20 |
| **Audience** | Builders, PortSwigger take-home reviewers |
| **Related** | [`01-PRD-MVP.md`](01-PRD-MVP.md) · [`13-HANDOFF.md`](13-HANDOFF.md) · [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) · [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) · [`08-COMPARE-ALGORITHM-AUDIT.md`](08-COMPARE-ALGORITHM-AUDIT.md) · [`09-OLLAMA-LAWYER-ASSISTANT-PRD.md`](09-OLLAMA-LAWYER-ASSISTANT-PRD.md) · [`10-LAWYER-WISHLIST-SPRINTS.md`](10-LAWYER-WISHLIST-SPRINTS.md) · [`CLAUDE_PORTSWIGGER.md`](CLAUDE_PORTSWIGGER.md) (vision only) |

**Conflict rule:** This checkpoint *describes* what shipped vs the PRD. The PRD remains scope authority for Must/Should/Won’t. Vision ideas in `CLAUDE_PORTSWIGGER.md` stay out of MVP unless listed as Must/Should there.

---

## 1. Vision vs what we shipped

| Horizon | Intent | Where we are |
|--------|--------|----------------|
| **Promise** | Upload → playbook → flag/counter → decide → remember | **Shipped** |
| **Principle** | AI proposes · playbook decides · lawyer confirms | **Held** |
| **MVP (PRD)** | GitHub/zip Loom demo (venv, no hosted deploy) | **~90–95% Must** |
| **Lawyer agents + wishlist** | Co-pilots, catalogue, undo, audit, help | **Shipped** |
| **Vision** (`CLAUDE_PORTSWIGGER.md`) | ReAct, hash-chain, PII suite, evals | **In progress** (V1–V5 track) |

---

## 2. Scorecard (2026-07-20)

### Goals G1–G10 — **Done**

### Journeys A–E — **Done** (incl. E2 starter, GapSuggest F27)

### Compare — **L0 + L1 + L2 shipped** (`layer_llm.py`; optional when `FAKE_LLM=0`)

### Feature snapshot

| Feature | Status |
|---------|--------|
| Upload PDF / DOCX / TXT (10 MB cap) | Yes (V1) |
| Security halt + AI adjudicator | Yes |
| L0/L1/L2 playbook flags | Yes |
| Magical LLM agents | Yes |
| Memory / Override / Undo / Audit | Yes |
| Contracts catalogue + Help | Yes |
| PII redaction before cloud LLM | V2 track |
| Missed clause → Activate | V3 track |
| Hash-chain audit | V4 track |
| Evals smoke | V5 track |
| SSO / ReAct | No (Won’t / deferred) |

**Remaining MVP Could:** F21 (PII), F22 (missed clause) — implementing in V2/V3.

---

## 3. Secure LLM layers

Shape unchanged: sanitize → detect → adjudicate → fence → structured output → fail-safe Fake. V2 adds PII redaction on outbound LLM payloads; V4 adds hash-chained `AuditEvent`.
