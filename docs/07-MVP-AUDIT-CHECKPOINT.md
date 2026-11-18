# MVP audit checkpoint

**Purpose:** Dated scorecard of what shipped vs the PRD (2026-07-20). Scope authority remains [`01-PRD-MVP.md`](01-PRD-MVP.md). Compare detail: [`08-COMPARE-ALGORITHM-AUDIT.md`](08-COMPARE-ALGORITHM-AUDIT.md).

| | |
|---|---|
| **Audience** | Builders, PortSwigger reviewers |
| **Related** | [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) · [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) · [`09-OLLAMA-LAWYER-ASSISTANT-PRD.md`](09-OLLAMA-LAWYER-ASSISTANT-PRD.md) · [`13-HANDOFF.md`](13-HANDOFF.md) · [`16-CURRENT-ARCHITECTURE.md`](16-CURRENT-ARCHITECTURE.md) |

---

## Horizons

| Horizon | Intent | Status |
|--------|--------|--------|
| Promise | Upload → playbook → flag/counter → decide → remember | Shipped |
| Principle | AI proposes · playbook decides · lawyer confirms | Held |
| MVP (PRD) | Zip/GitHub Loom demo on local venv | ~90-95% Must |
| Lawyer agents + wishlist | Co-pilots, catalogue, undo, audit, help | Shipped |
| Stretch (V2-V5) | PII redaction, missed-clause Activate, hash-chain audit, evals smoke | In progress |
| Vision | LangGraph / ReAct orchestration | Planned ([`15-LANGGRAPH-MULTI-AGENT-ARCHITECTURE.md`](15-LANGGRAPH-MULTI-AGENT-ARCHITECTURE.md)) |

---

## Scorecard

| Item | Status |
|------|--------|
| Goals G1-G10 | Done |
| Journeys A-E (incl. E2 starter, GapSuggest) | Done |
| Compare L0 + L1 + L2 candidate judge | Done (auto-on when `FAKE_LLM=0`; discovery planned; see [`08`](08-COMPARE-ALGORITHM-AUDIT.md)) |
| Upload PDF / DOCX / TXT | Yes |
| Security halt + AI adjudicator | Yes |
| Memory / Override / Undo / Audit | Yes |
| Contracts catalogue + Help | Yes |
| Magical LLM agents | Yes |
| PII redaction before cloud LLM | V2 |
| Missed clause → Activate | V3 |
| Hash-chain audit | V4 |
| Evals smoke | V5 |
| SSO | Deferred |

### Lawyer wishlist (folded from former sprint list)

| Focus |
|-------|
| Contracts catalogue + paginated History |
| Undo / revoke override / playbook restore + CRUD APIs |
| False-positive report + playbook auditor |
| PDF pane + finding evidence |
| REST lists + AuditEvent |
| `/help/` tutorial |

**Governance:** Accept updates memory / overrides; golden playbook changes only on deliberate Activate (or restore).

---

## Secure LLM layers

Sanitize → detect → adjudicate → fence → structured output → fail-safe Fake. V2 adds PII redaction on outbound LLM payloads; V4 adds hash-chained `AuditEvent`.
