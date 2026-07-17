# CLAUDE.md — RedlineGuard Agent Guide

> **MVP scope first.** Before following this file, read:
> 1. [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md)
> 2. [`01-PRD-MVP.md`](01-PRD-MVP.md)
> 3. [`02-MVP-IMPLEMENTATION.md`](02-MVP-IMPLEMENTATION.md)
>
> This document is the **broader vision / engineering wishlist**. Anything here that is not a PRD **Must/Should** is **out of MVP** (including ReAct agents, full audit hash chain, multi-provider routing, Chroma-at-scale, rich dashboard). Prefer Django + playbook + fence + decisions as in the MVP implementation guide — **do not** switch to Streamlit from the Gemini brainstorm.

Guidance for Cursor (and humans) working in this repo. Read the MVP trio above first; use this file for post-MVP depth and naming inspiration.

---

## 0. What this is

**RedlineGuard** is an AI-assisted commercial contract review tool built for PortSwigger's in-house legal team as a take-home exercise for the AI Pioneer role.

It is a security-first evolution of **PactPilot** — the 1st Runner-Up from the IADS Agentic AI Hackathon (Essex + Oracle, June 2026), designed and pitched by Ankit Yadav as Team Lead of a 6-person team.

PactPilot was a hackathon prototype scoped to a 48-hour build: a small-business founder drops in a contract, gets a 30-second verdict, chats with the doc, moves on. Stateless, no login, single-shot.

RedlineGuard inherits PactPilot's design discipline (schema-first API contract, LangGraph node-per-slice architecture, canned responses from day one) and evolves it for a fundamentally different user, tempo, and venue.

---

## 1. The five things that make RedlineGuard novel, not derivative

Every architecture decision below traces back to at least one of these.

**1.1 Different user, different tempo.** PactPilot serves a small-business founder reviewing one contract in a moment of decision. RedlineGuard serves a legal reviewer working through a queue that gets longer than the day. This means: batch UI, memory across sessions, learning from past decisions, a dashboard for the team lead. PactPilot was a moment. RedlineGuard is a workflow.

**1.2 Security is the feature, not an afterthought.** PactPilot has one line about not being legal advice. RedlineGuard is built for a security company, so it treats itself as a potential attack surface. Prompt injection defence, PII redaction, output validation, model routing by sensitivity, and an audit trail with a hash chain — all mandatory, all visible in the UI. If your instinct is to skip a security layer to save time, the answer is to skip a UI polish instead.

**1.3 A learning loop instead of a chat window.** PactPilot has a Q&A chat with the current doc. RedlineGuard has a memory of every past contract's decisions. Every accepted redline becomes precedent for future drafts. Every rejection is captured with (optional) reasoning. The retrieval index is the point. Chat is not.

**1.4 Multi-provider LLM with local fallback, not OCI-only.** PactPilot was OCI-only for hackathon reasons. RedlineGuard runs on a multi-provider fallback (Groq, Mistral, Gemini, OpenRouter, Cohere) and routes sensitive contracts to a local model (Ollama + Gemma-2B) so PII never leaves the machine. This is inherited from MimWise's production pattern, not from PactPilot.

**1.5 Django, not FastAPI.** PactPilot planned FastAPI + a Lovable-built React frontend. RedlineGuard is Django, server-rendered with Bootstrap. Reasons: (a) the reviewer's UI is the point, and Django templates ship faster than another React app; (b) it matches MimWise's stack, so scaffolding is proven; (c) Django's admin gives us the audit-log viewer and config editor almost for free.

**Read later (added teaching sections):** Section 17 glossary · Section 18 ReAct draft agent · Section 19 evals · Section 20 web/DB security.

---

## 2. What we inherit from PactPilot's design discipline

Read these three principles as gospel — they saved PactPilot's demo from disaster and they will save yours.

**2.1 The API contract is frozen from day one.** `apps/api/schemas.py` defines Pydantic models for every request and response the system will ever produce. The UI is built against these schemas. If a field is not yet computed, the endpoint returns `None` or `[]` for that field but the shape is stable. Never rename or reshape a field without updating the schema, the tests, and every consumer in the same commit.

**2.2 Every node fills its own slice, testable in isolation.** The LangGraph pipeline is composed of small nodes. Each node has a single responsibility, a Pydantic input schema, a Pydantic output schema, and a unit test with a canned input. Independent nodes run concurrently. This is what makes the 40-second latency budget possible.

**2.3 Canned responses from day one.** Before any LLM call works, the API returns a hand-written `AnalysisResult` for every endpoint. The UI can be built and demoed against this canned data. Real pipeline nodes replace the canned response slice by slice. The UI never breaks because a depth field is `None`.

---

## 3. Tech stack (evolved from PactPilot)

| Layer | PactPilot (planning) | RedlineGuard (this build) | Why the change |
|---|---|---|---|
| Backend | FastAPI 3.11 | Django 5 + Django REST Framework | Server-rendered UI is the product; Django admin is free audit-log viewer |
| Frontend | Lovable-generated React + Vite + TS | Django templates + Bootstrap 5 + minimal vanilla JS | Fastest path; matches MimWise; no split-repo overhead |
| LLM orchestration | LangChain + LangGraph on OCI Gen AI | LangChain + LangGraph, multi-provider fallback + local Ollama | Production-grade reliability and privacy routing |
| Vector store | Oracle 23ai AI Vector Search | ChromaDB (local, persisted) with FAISS as swap-in | Local demo, no cloud dependency |
| Storage | OCI Object Storage | Local filesystem for the demo, S3-compatible interface for production | Local demo; interface makes S3 swap trivial |
| Deploy | OCI Compute (Ampere) | Docker Compose for demo | Reviewers can run it in one command |
| PII detection | Not addressed | spaCy en_core_web_sm + regex, with reversible token replacement | Security requirement, not optional |
| Injection defence | Not addressed | Regex patterns + LLM-as-judge second check, halts pipeline on detection | Security requirement, not optional |
| Audit trail | Not addressed | Postgres append-only log with hash chain | Security requirement, not optional |

**All dependencies pinned.** All secrets loaded from `.env` via `django-environ`. All external calls behind a client class with a `FAKE_LLM=1` mode that returns fixtures — so the whole app runs with no cloud credentials for local dev.

---

## 4. Repo layout

```
redlineguard/
├── CLAUDE.md                        # this file
├── README.md                        # public-facing, human-first
├── docker-compose.yml               # one-command demo
├── .env.example                     # never commit .env itself
├── requirements.txt
├── manage.py
├── redlineguard/                    # Django project
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── contracts/                   # upload, storage, extraction
│   │   ├── models.py                # Contract, Clause
│   │   ├── views.py                 # upload, review
│   │   ├── extractors.py            # PDF, text
│   │   ├── segmenter.py             # inherit from PactPilot: text -> Clause[]
│   │   └── tests/
│   ├── triage/                      # classification, flagging
│   │   ├── graph.py                 # LangGraph pipeline for triage
│   │   ├── nodes/                   # one file per node
│   │   │   ├── classify.py
│   │   │   ├── flag_clauses.py
│   │   │   └── rank_severity.py
│   │   ├── prompts/                 # prompt templates live beside nodes
│   │   └── tests/
│   ├── drafting/                    # counter-language generation (ReAct agent)
│   │   ├── graph.py                 # Thought → Action → Observation loop
│   │   ├── tools.py                 # tool menu the agent can call
│   │   ├── nodes/
│   │   │   ├── agent.py             # LLM decides next Thought + Action
│   │   │   ├── tool_executor.py     # runs tools, returns Observation
│   │   │   ├── loop_guard.py        # max iterations / force halt
│   │   │   └── produce_diff.py      # unified diff + HTML render (post-agent)
│   │   └── tests/
│   ├── security/                    # the perimeter
│   │   ├── sanitiser.py             # strip injection patterns
│   │   ├── injection_detector.py    # regex + LLM-as-judge
│   │   ├── redactor.py              # spaCy + regex, reversible
│   │   ├── router.py                # local vs cloud routing decision
│   │   └── tests/
│   ├── learning/                    # feedback loop, vector memory
│   │   ├── vector_store.py          # ChromaDB wrapper
│   │   ├── precedent.py             # store/retrieve accepted drafts
│   │   ├── feedback.py              # capture reject/edit signals
│   │   └── tests/
│   ├── audit/                       # append-only log with hash chain
│   │   ├── models.py                # AuditEntry
│   │   ├── logger.py                # write with hash of previous
│   │   ├── verifier.py              # verify chain integrity
│   │   └── tests/
│   ├── governance/                  # config-driven rules, dashboard
│   │   ├── models.py                # ConfigVersion
│   │   ├── config_loader.py         # hot-reload YAML
│   │   ├── views.py                 # dashboard, config editor
│   │   └── tests/
│   ├── llm/                         # provider abstractions
│   │   ├── base.py                  # abstract LLMClient
│   │   ├── multi_provider.py        # Groq, Mistral, Gemini, OpenRouter, Cohere
│   │   ├── local_ollama.py          # Gemma-2B via Ollama
│   │   ├── fake.py                  # FAKE_LLM=1 fixtures
│   │   └── tests/
│   └── api/                         # DRF endpoints + shared schemas
│       ├── schemas.py               # FROZEN Pydantic contracts
│       ├── serializers.py
│       ├── views.py
│       └── tests/
├── templates/                       # Django templates
│   ├── base.html
│   ├── upload.html
│   ├── review.html
│   ├── security_alert.html
│   ├── dashboard.html
│   ├── audit_log.html
│   └── config.html
├── static/
│   ├── css/
│   └── js/
├── config/
│   ├── clauses.yaml                 # taxonomy — governance edits this
│   ├── redaction.yaml               # PII patterns
│   └── routing.yaml                 # local vs cloud rules
├── data/
│   ├── samples/                     # sample contracts for demo
│   └── precedent_seed.jsonl         # seed precedent for the learning loop
├── scripts/
│   ├── seed_precedent.py            # load precedent_seed.jsonl into vector store
│   └── generate_sample_contracts.py # for demo
├── evals/                           # LLM + agent evaluation harness (Section 19)
│   ├── datasets/                    # curated fixtures with expected outcomes
│   ├── runners/                     # one script per eval suite
│   ├── judges/                      # LLM-as-judge rubric prompts
│   └── reports/                     # timestamped JSON results (gitignored contents OK)
└── docs/
    ├── architecture.md              # links to diagrams
    ├── security.md                  # OWASP LLM Top 10 mapping + web/DB hygiene
    ├── owasp_llm_top10.md
    └── writeup.md                   # the submission writeup
```

---

## 5. The frozen API contract

`apps/api/schemas.py` defines every shape. **Do not modify these without updating templates, views, tests, and this doc in the same commit.**

```python
# apps/api/schemas.py — FROZEN. Read before you write.

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

# ---- Domain objects ----

class Clause(BaseModel):
    """A single clause inside a contract. Char offsets drive UI highlighting."""
    id: str                                # e.g. "5.2"
    heading: str                           # e.g. "Indemnification"
    text: str
    start: int                             # char offset in original doc
    end: int                               # char offset in original doc

class Flag(BaseModel):
    """A flagged clause needing human attention."""
    clause_id: str
    category: str                          # from config/clauses.yaml
    severity: Literal["low", "medium", "high"]
    reasoning: str                         # plain-English why-flagged

class Precedent(BaseModel):
    """A past accepted redline referenced when drafting."""
    id: str
    contract_id: str
    clause_id: str
    original_text: str
    accepted_redline: str
    accepted_at: datetime

class Draft(BaseModel):
    """A proposed redline for a flagged clause."""
    clause_id: str
    original_text: str
    proposed_redline: str
    reasoning: str
    precedents: list[Precedent]            # what the draft was grounded in
    confidence: float                      # 0.0-1.0

class AuditEntry(BaseModel):
    """Append-only log entry with hash chain."""
    id: int
    timestamp: datetime
    contract_id: Optional[str]
    event_type: str                        # e.g. "injection_caught", "draft_accepted"
    actor: str                             # "user:sarah" or "model:groq-llama-3.1-70b"
    summary: str
    payload_json: str                      # full detail
    prev_hash: str
    hash: str

# ---- Response shapes ----

class TriageResult(BaseModel):
    """Response from /api/contracts/<id>/triage/"""
    contract_id: str
    contract_type: str                     # "mutual_nda", "order_form", etc.
    contract_type_confidence: float
    risk_score: Literal["low", "medium", "high"]
    flags: list[Flag]
    clauses: list[Clause]
    routed_to: Literal["local", "cloud"]
    latency_ms: int

class DraftResult(BaseModel):
    """Response from /api/contracts/<id>/clauses/<clause_id>/draft/"""
    draft: Draft
    latency_ms: int

class DecisionInput(BaseModel):
    """POST body for /api/contracts/<id>/clauses/<clause_id>/decision/"""
    decision: Literal["accept", "edit", "reject"]
    edited_text: Optional[str] = None      # required if decision == "edit"
    reject_reason: Optional[str] = None    # optional if decision == "reject"

class SecurityEvent(BaseModel):
    """Response when a security check blocks the pipeline."""
    event_id: str
    event_type: Literal["injection", "pii_leak", "schema_fail", "unsupported_format"]
    snippet: str                           # what was flagged (redacted if PII)
    explanation: str                       # plain-English for Sarah
    audit_entry_id: int
```

---

## 6. LangGraph pipeline: triage flow

Triage is the entry graph. Draft is a second graph triggered per clause on demand.

```
                    ┌──────────────────┐
                    │ upload_and_extract│    apps/contracts/segmenter.py
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ sanitise_input   │    apps/security/sanitiser.py
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ detect_injection │    apps/security/injection_detector.py
                    └────┬─────────┬───┘
                    safe │         │ malicious
                         ▼         ▼
                                halt + log + SecurityEvent
                    ┌──────────────────┐
                    │  redact_pii      │    apps/security/redactor.py
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  route_model     │    apps/security/router.py
                    └────┬─────────┬───┘
                sensitive│         │ standard
                         ▼         ▼
                    ┌──────┐   ┌──────┐
                    │local │   │cloud │
                    │Ollama│   │Groq  │
                    └───┬──┘   └───┬──┘
                        └────┬─────┘
                             ▼
                    ┌──────────────────┐
                    │ classify         │    apps/triage/nodes/classify.py
                    │ flag_clauses     │    apps/triage/nodes/flag_clauses.py
                    │ rank_severity    │    apps/triage/nodes/rank_severity.py
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ validate_schema  │    Pydantic; on fail, fallback path
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ unredact + return│
                    └──────────────────┘
```

Each node has a canned response so the UI works end-to-end from day one with `FAKE_LLM=1`.

---

## 7. Security perimeter — non-negotiable

**7.1 Sanitiser (apps/security/sanitiser.py)**
Strips known injection markers from contract text before it ever reaches an LLM.

Patterns to strip:
- Instruction-override phrases (regex-matched, config-driven)
- System-prompt spoofing markers (`<|system|>`, `[INST]`, etc.)
- Encoded payloads (base64-looking blobs, hex-heavy sequences over 100 chars in what should be prose)
- Zero-width Unicode characters

Test coverage: `apps/security/tests/test_sanitiser.py` with a corpus of 20 real-world injection attempts (embed in test fixtures, do not commit any live payload).

**7.2 Injection detector (apps/security/injection_detector.py)**
Two-stage:
- Stage 1: regex/rule-based fast check
- Stage 2: LLM-as-judge (uses a smaller, trusted model with a strict system prompt) as a second opinion

If either stage flags high confidence: halt the pipeline, log a `SecurityEvent`, return the modal to the user.

**7.3 PII redactor (apps/security/redactor.py)**
- spaCy `en_core_web_sm` NER for names, orgs, locations, dates
- Regex for emails, phone numbers, national IDs, financial account numbers, IP addresses
- Replacement: `PERSON_1`, `EMAIL_1`, etc. Deterministic mapping stored in memory for the request duration only.
- Reversal happens after LLM response, before returning to the user.

**7.4 Router (apps/security/router.py)**
Reads `config/routing.yaml`. Rules like:
```yaml
- name: sensitive_by_marker
  match: any_of: ["CONFIDENTIAL", "PROPRIETARY", "RESTRICTED"]
  route: local

- name: sensitive_by_pii_density
  match: pii_count_gte: 5
  route: local

- name: default
  route: cloud
```

Never sends "sensitive" content to cloud. If a rule route is `local` and the local model is unavailable, the pipeline halts with a security event rather than falling back to cloud.

**7.5 Schema validator**
Every LLM response is parsed against its Pydantic schema. On fail: log the raw output, retry once with a corrective prompt, then halt with a schema-fail event.

**7.6 Audit logger (apps/audit/logger.py)**
Every write is a new row in `AuditEntry` table. Each row's `hash` = sha256(`prev_hash` + serialised payload). Tampering with row N invalidates rows N+1 onwards. Provide a `verify_chain()` method for the UI's "Verify integrity" button.

---

## 8. The learning loop (apps/learning/)

**8.1 Vector store (apps/learning/vector_store.py)**
ChromaDB with cosine similarity. One collection: `precedents`. Persist to disk under `data/chroma/`.

**8.2 Seeding (scripts/seed_precedent.py)**
Reads `data/precedent_seed.jsonl` (5-10 hand-written precedents covering common clauses). Loads into vector store on first run.

**8.3 Retrieval (apps/learning/precedent.py)**
Given a flagged clause, retrieve top-K similar past precedents by cosine similarity on embedded clause text. K=3 default.

**8.4 Feedback capture (apps/learning/feedback.py)**
- On accept: the accepted draft becomes a new precedent, added to vector store.
- On edit: the edited version becomes the precedent, and the edit distance from AI draft is logged.
- On reject: the clause + reject reason (if provided) is stored as an anti-example. Anti-examples are retrieved alongside precedents during drafting and used as negative context in the prompt.

**8.5 No fine-tuning.** Learning happens purely via retrieval-augmented prompting. This is a deliberate choice: no model weights change, so there is no data poisoning risk (OWASP LLM03).

---

## 9. Build sequence — 3 days, milestone by milestone

Do not skip ahead. Each milestone unlocks the next.

### Day 1: Foundations + canned pipeline

**M1: Repo scaffold and Docker Compose**
- Django project + apps as per Section 4
- `docker-compose.yml` with Postgres + Django + (later) Ollama
- `.env.example` with placeholders
- `pip install`, migrations run, superuser created
- `curl localhost:8000/api/health/` returns `{"status": "ok"}`

**M2: The frozen schemas**
- Write `apps/api/schemas.py` verbatim from Section 5
- Write tests that validate every schema against a sample fixture

**M3: Canned triage endpoint**
- `POST /api/contracts/upload/` accepts a PDF, returns `{"contract_id": "..."}`
- `POST /api/contracts/<id>/triage/` returns a hand-written `TriageResult` with 3 flagged clauses
- UI can render the Review page against this canned data

**M4: Contract ingestion**
- `apps/contracts/extractors.py`: PDF -> text (pdfminer or PyMuPDF)
- `apps/contracts/segmenter.py`: text -> `list[Clause]` (inherit segmentation logic from PactPilot planning)
- Store original + hash in `Contract` model

**End of Day 1: A user can upload a real PDF, see extracted text, and see three hand-canned flagged clauses on the Review page. The pipeline is fake but the UI is real.**

---

### Day 2: Security + real LLM triage + draft

**M5: Security perimeter**
- Sanitiser, injection detector (stage 1 regex only for M5), PII redactor
- All three tested with fixtures
- `SecurityEvent` returned from any endpoint that halts

**M6: Multi-provider LLM client**
- `apps/llm/base.py`: abstract `LLMClient` with `complete(prompt, schema)`
- `apps/llm/multi_provider.py`: iterates providers in order; retries once on transient error; validates against schema
- `apps/llm/fake.py`: returns fixtures. `FAKE_LLM=1` env var switches all clients to fake.
- `apps/llm/local_ollama.py`: Gemma-2B via Ollama's HTTP API

**M7: Real triage nodes**
- `apps/triage/nodes/classify.py`: contract type + confidence
- `apps/triage/nodes/flag_clauses.py`: given clauses + taxonomy, produce flags
- `apps/triage/nodes/rank_severity.py`: severity assignment
- All nodes are LangGraph nodes with Pydantic in/out schemas
- Replace canned response with real pipeline slice by slice; canned fallback stays for depth fields

**M8: Draft engine (ReAct agent — see Section 18)**
- `apps/drafting/tools.py`: `search_precedents`, `check_policy`, `redact_pii`, `generate_draft_body`, `verify_schema`, `escalate_to_human`
- LangGraph loop: Agent (LLM) → Tool Executor → Loop guard (max 10 iterations)
- Triage stays a fixed chain (classify / flag / rank); only drafting is agentic
- `apps/drafting/nodes/produce_diff.py`: unified diff + HTML render after the agent returns
- `POST /api/contracts/<id>/clauses/<clause_id>/draft/` returns `DraftResult` (include reasoning trace in audit log)
- Write `evals/runners/run_drafting.py` + trajectory eval alongside the agent (Section 19)

**M9: Audit trail**
- `AuditEntry` model with hash chain
- Every LLM call, every security event, every human decision logged
- Django admin exposes the audit log for read-only inspection

**End of Day 2: A real contract goes through the real pipeline, gets classified, flagged, and drafted. Injection detection actually catches malicious inputs. Local model handles sensitive routes.**

---

### Day 3: Learning + governance + polish + writeup

**M10: Learning loop**
- Seed 5-10 hand-written precedents in `data/precedent_seed.jsonl`
- `scripts/seed_precedent.py` loads them into ChromaDB
- Feedback capture on accept/edit/reject writes back to vector store
- Verify: after 3 accepts, a similar new clause retrieves those 3 as precedents

**M11: Governance**
- Config editor for `clauses.yaml`, `redaction.yaml`, `routing.yaml`
- Hot-reload without restart
- Version history (git-style diff view) stored in `ConfigVersion` model

**M12: Dashboard**
- Metric cards: contracts processed, median time, auto-approve rate, security events
- Simple bar chart of top clause categories flagged
- One line chart: draft acceptance rate over time

**M13: LLM-as-judge (Stage 2 injection detection)**
- Add the second-opinion LLM call to injection detector
- Keep it opt-in via env var so demos can be deterministic

**M13b: Eval harness (Section 19)**
- Curate datasets under `evals/datasets/` (start with classification — 20–25 contracts)
- Runners for classification, flagging, injection, PII; trajectory + draft judge for the ReAct agent
- `python -m evals.runners.run_all` produces timestamped reports; quote real numbers in README

**M14: Writeup + Loom video**
- README with architecture, security choices (Section 20.7 paragraph), honest limitations, how-to-run, eval table
- 5-8 minute Loom walking through: upload, triage, injection catch, draft (show tool trace if demable), accept, dashboard, config change, audit log

**End of Day 3: Zip and submit.**

---

## 10. Cursor conventions — read before prompting Cursor

**10.1 Never accept generated code without reading it.** Cursor will happily generate code that passes tests but embeds test-case shortcuts in business logic. Every generated file gets a manual read pass before commit. See the PortSwigger take-home brief — this exact failure mode is what they are testing you against.

**10.2 Ask Cursor for one node at a time, not one graph.** Prompts like "build the entire triage pipeline" get worse output than "implement `apps/triage/nodes/classify.py` following the schema in `apps/api/schemas.py` line 62-70, with a unit test that mocks the LLM client."

**10.3 Point Cursor at the schema, not at your imagination.** Whenever a prompt would benefit, prefix with "read `apps/api/schemas.py` and `apps/security/tests/test_sanitiser.py` before writing this."

**10.4 The 'why' comment beats the 'what' comment.** In generated code, delete `# increment counter` style comments and replace with `# increment because …`. Cursor over-comments the obvious.

**10.5 Never let Cursor invent a schema field.** If Cursor generates `flag.confidence` and the schema does not have `confidence` on `Flag`, that is a schema violation. Reject and re-prompt with the schema quoted.

**10.6 Ask Cursor for the failing test first.** Test-first prompts produce better code than code-first prompts. Write the failing test, then ask Cursor to make it pass.

**10.7 Never accept generated regex without a test.** Especially for the injection detector. Every regex needs at least 3 positive and 3 negative test cases.

**10.8 Ask "what did you not implement?" at the end of every session.** Cursor often skips edge cases silently. Prompt: "list every path you did not handle in this file and rank by risk."

---

## 11. Running locally

```bash
# Clone, install
git clone <repo>
cd redlineguard
cp .env.example .env    # fill in placeholders; FAKE_LLM=1 for no-cloud dev
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser

# Seed precedent (once)
python scripts/seed_precedent.py

# Run
docker compose up               # brings up postgres + django + ollama
# or
python manage.py runserver

# Open http://localhost:8000
```

**No cloud access is ever required to run the app.** `FAKE_LLM=1` stubs every provider. The local Ollama container ships with Gemma-2B pre-pulled.

---

## 12. Guardrails — what Cursor must not do

- **Do not add auth beyond Django admin.** No SSO, no OAuth, no RBAC. This is a demo.
- **Do not add a real background job queue.** No Celery, no Redis Queue. Pipeline runs synchronously; if it takes too long, that is a design signal, not a scaling problem.
- **Do not add analytics beacons, telemetry, or third-party tracking.** This is a legal tool. Analytics endpoints inside the app are fine.
- **Do not add "delight" animations, gamification, or emoji-heavy UI copy.** Sarah is a lawyer. Tone is calm, precise, direct.
- **Do not commit secrets, `.env`, `~/.oci/config`, wallets, or any private key.** Use `.env.example`.
- **Do not silently downgrade a security check to save latency.** If injection detection is slow, make it faster or asynchronous, but never optional.
- **Do not add a "chat with the doc" feature.** That was PactPilot's differentiator. RedlineGuard's differentiator is the learning loop, not the chat.
- **Do not fine-tune any model.** All learning is retrieval-based. This is a security property, not a limitation.
- **Do not concatenate user input into system prompts.** Ever. Contract text goes as data, not as instructions. This is the single most common source of prompt injection.
- **Do not commit any live injection payload as test data.** Reference by category and reproduce mechanism, never verbatim.

---

## 13. The submission zip contents

At the end, the zip should contain:

```
redlineguard/
├── (full source tree)
├── README.md                        # architecture + security + honest limitations + how-to-run
├── docs/
│   ├── PRD.pdf                      # the full PRD we already wrote
│   ├── VisualCompanion.pdf          # the companion doc for screens/flows
│   └── architecture_diagram.png     # exported from Claude visualisation
├── LOOM_LINK.md                     # 5-8 minute walkthrough
├── data/samples/                    # 3-5 sample contracts to demo on
└── LICENCE                          # MIT for the demo code (make clear it is demo code)
```

---

## 14. Honest disclosure to PortSwigger in the README

The README must include a paragraph like:

> RedlineGuard is a fresh take-home build. Its architectural discipline (schema-first API contract, LangGraph node-per-slice pipeline, canned responses from day one) is inherited from PactPilot, an earlier hackathon prototype I led. Its security perimeter, learning loop, multi-provider LLM layer, and Django-based UI are new for this exercise. This is a demo, not a production system; the sections marked "out of scope" in the PRD would be needed before deploying to a real legal team.

That paragraph does two things: it credits PactPilot honestly, and it names what is genuinely new. Do not skip it.

Also paste the **Security posture** paragraph from Section 20.7 near the top of the README (right after the intro). Quote real eval numbers from `evals/reports/` (Section 19) — never invent them.

---

## 15. Test discipline

- Every node has a unit test with the LLM mocked.
- Every schema has a validation test.
- Every security check has 3 positive + 3 negative fixtures.
- At least one end-to-end test that walks upload → triage → draft → accept → precedent stored, all with `FAKE_LLM=1`.
- **Evals are not optional polish** — see Section 19. Component evals (classification, flagging, injection, PII) run on prompt/node changes; agent trajectory + LLM-as-judge draft evals run nightly / before the Loom.
- When Cursor implements a feature, ask it to write the matching eval runner in the same session.
- No commit to `main` without a green CI run. (For a demo, GitHub Actions with `pytest` on push is enough.)

---

## 16. Definition of done

RedlineGuard is done when:

- [ ] `docker compose up` on a clean machine gets a reviewer to the Upload screen in under 60 seconds
- [ ] Uploading a sample contract shows a real Review screen with real flags in under 15 seconds (cloud) or 45 seconds (local)
- [ ] An intentional injection payload triggers the Security Alert modal, not a silent failure
- [ ] Accepting 3 drafts on similar clauses causes the 4th similar clause to retrieve those 3 as precedents
- [ ] Editing `config/clauses.yaml` and reloading changes the flag behaviour without restart
- [ ] The Audit Log shows every event with a verified hash chain
- [ ] The README explains every security choice and honest limitation
- [ ] `evals/` has curated datasets + runners; README quotes real numbers from the latest report
- [ ] Draft engine is a ReAct agent with tool calling (Section 18); triage remains a fixed chain
- [ ] Production security settings live in `settings_production.py` and are named in the README (Section 20)
- [ ] A 5-8 minute Loom walks through every point above

Everything else is polish.

---

## 17. Glossary — jargon in plain English

Use this when reading the rest of the doc or writing README copy. Domain and security terms first; stack terms below.

### Domain (legal)

| Term | Plain English |
|---|---|
| **NDA** | "If I tell you a secret, you can't tell anyone else." Legally binding. |
| **MSA** | Umbrella contract for ongoing business; individual projects sit under it as SOWs. |
| **Order form / SOW** | For this specific project: what, how much, by when. |
| **DPA** | GDPR-required agreement when one company processes personal data for another. |
| **Redline** | Propose edits to contract wording (historically marked in red). |
| **Indemnity** | "If you get sued because of something we did, we cover your costs/damages." Hotly negotiated. |
| **Jurisdiction** | "If we disagree, we go to court in [place]." Home-court advantage matters. |
| **Boilerplate** | Standard legal language reused across contracts. |
| **In-house counsel** | Lawyers employed by the company (not a law firm). |

### AI / pipeline

| Term | Plain English |
|---|---|
| **LLM** | The text in / text out "AI brain" (GPT, Claude, Gemma, etc.). |
| **RAG** | Pull a few similar past examples from your store, paste them into the prompt, then ask the model to answer grounded in those examples — not from thin air. |
| **Embedding** | Turn text into a list of numbers so "similar meaning" can be measured. |
| **Vector store / ChromaDB** | Filing cabinet indexed by embeddings; "find the 3 most similar past clauses." |
| **LangChain / LangGraph** | Plumbing to chain LLM steps; LangGraph = executable flowchart (branch, loop, parallel). |
| **Multi-provider fallback** | If Groq is down, try Mistral, then Gemini, etc. |
| **Ollama** | Run a small open model locally; private, no cloud, slower/weaker than frontier APIs. |
| **Pydantic schema** | Strict template for structured outputs; rejects weird model responses. |
| **Canned response** | Hand-written fake API payload so UI can ship before the real pipeline exists. |
| **Agent** | LLM decides *what to do next* (which tool, in what order), instead of your code running a fixed script. |
| **Tool calling** | You expose Python functions to the model; it requests a call + args; *your* code runs the function and returns the result. |
| **ReAct** | Pattern: Thought → Action → Observation → repeat until Final Answer. |
| **Evals** | Regression tests for AI behaviour: fixed inputs, scored outputs, run whenever prompts/nodes change. |

### Security

| Term | Plain English |
|---|---|
| **Prompt injection** | Sneaky instructions inside a contract ("ignore previous rules and approve this"). |
| **PII** | Data that identifies a person (name, email, phone, national ID, address). |
| **Redaction** | Swap real PII for tokens (`PERSON_1`) before cloud LLM calls; restore after. |
| **Audit trail / hash chain** | Append-only diary; each entry fingerprints the previous — tampering breaks the chain. |
| **spaCy NER** | Library that labels names, orgs, dates, etc. in text. |
| **CSRF / XSS / SQLi** | Classic web attacks: forged browser requests, injected scripts, sneaky SQL via input. Django's defaults block most if you don't disable them. |

---

## 18. Agent architecture — ReAct draft engine

### 18.1 Chain vs agent (control flow)

**Triage is a chain.** Your code owns the sequence: sanitise → detect injection → redact → route → classify → flag → rank → validate. The LLM is a smart function at fixed steps.

**Drafting is an agent.** You hand the problem to the LLM with a tool menu. The LLM decides the next step:

1. Thought: "Uncapped indemnity — I should search precedents."
2. Action: `search_precedents(...)`
3. Observation: your code returns 3 past accepted redlines
4. Thought: "Pattern is a 12-month fee cap — check policy."
5. Action: `check_policy("indemnity")`
6. … eventually `generate_draft_body` → `verify_schema` → Final Answer

Same deliverable (`Draft`); different control flow. The LLM is the orchestrator; your code only provides tools and enforces limits.

### 18.2 What a "tool" is

A tool is a normal Python function described to the LLM (name, purpose, args, return shape). The model does **not** execute it — it emits "call X with args Y". Your executor runs X, logs it, and feeds the result back as an Observation.

That means you can: log every call for audit, reject unknown tools, Pydantic-validate args, rate-limit, and refuse writes from inside the agent.

### 18.3 Tool menu (`apps/drafting/tools.py`)

| Tool | Role |
|---|---|
| `search_precedents(clause_text, top_k=3)` | Retrieve similar accepted redlines |
| `check_policy(clause_category)` | Load hard constraints from config |
| `redact_pii(text)` | Tokenise PII before any cloud-bound text leaves |
| `generate_draft_body(original, guidance, precedents)` | **Only** tool that invents new text |
| `verify_schema(draft)` | Self-check against `Draft` Pydantic model |
| `escalate_to_human(reason)` | Halt — allowed failure mode (OWASP LLM08 Excessive Agency) |

Design rules:

- Only one generative tool; everything else retrieves, checks, or halts.
- Agent is read/generate-only — **no DB writes**. Outer code writes after trajectory review.
- `escalate_to_human` is first-class, not a shame path.

### 18.4 LangGraph shape

```
                    ┌──────────────┐
                    │  Agent (LLM) │  emits Thought + Action
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │ Tool Executor│  runs tool → Observation
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  Loop guard  │  max 10 iterations, else force halt
                    └──────┬───────┘
              ┌────────────┴────────────┐
       not done → back to Agent         done → Final Answer (+ produce_diff)
```

State carries full conversation history so each turn sees prior Thought/Action/Observation.

### 18.5 Failure modes (defend these)

| Failure | Defence |
|---|---|
| Infinite loops | Hard cap (10 iterations) |
| Hallucinated tool name | Executor rejects unknown tools; return error Observation |
| Bad args | Pydantic-validate before invoke |
| Drafts without retrieval | Prompt: must call at least one search tool before `generate_draft_body` |
| Injection via Observation | Sanitise observations the same way you sanitise user input |
| Cost blowup | Track tokens/session; alert over budget |

### 18.6 Where NOT to use an agent

| Step | Agent? | Why |
|---|---|---|
| Classification | No | One input → one label |
| Flagging / severity | No | One input → structured list |
| **Drafting** | **Yes** | Needs lookup + policy + grounded generation |
| Explanation / why-flagged | No | One input → one explanation |

Rule of thumb: if you might need to look things up before answering, use an agent; otherwise a single `complete(prompt, schema)` call.

### 18.7 Why this matters for PortSwigger

- Auditability: every Thought/Action is loggable — "why this redline?" has a trace.
- Differentiator: most take-homes won't ship tool calling.
- Extensibility: new tools are config + function, not a rewrite.
- Matches how you'd level up from MimWise's fixed pipeline toward production agent patterns.

---

## 19. Evaluation harness (`evals/`)

Evals are regression tests for AI behaviour. Without them you prompt by vibes; with them you prompt by numbers. PortSwigger will notice an `evals/` folder with real reports.

### 19.1 Two levels

1. **Component (LLM) evals** — one call in isolation (classifier accuracy, flag precision/recall, injection FP/FN, PII recall).
2. **Agent / system evals** — end-to-end behaviour: trajectory (did it call the right tools?), draft quality (LLM-as-judge or properties), safety (malicious inputs).

### 19.2 Directory layout

```
evals/
├── datasets/
│   ├── classification.jsonl    # ~25 contracts → expected_type
│   ├── flagging.jsonl          # ~15 contracts → expected flags
│   ├── injection.jsonl         # 15 malicious + 15 benign
│   ├── pii_redaction.jsonl     # ~20 docs with known PII spans
│   └── drafting.jsonl          # ~10 clauses + acceptable draft properties
├── runners/
│   ├── run_classification.py
│   ├── run_flagging.py
│   ├── run_injection.py
│   ├── run_pii.py
│   ├── run_drafting.py         # LLM-as-judge + property checks
│   ├── run_trajectory.py       # ReAct tool-sequence checks
│   └── run_all.py
├── judges/
│   └── draft_judge_prompt.txt  # rubric 0–2 × 4 criteria
└── reports/                    # classification_YYYYMMDD_HHMMSS.json etc.
```

Each eval is: **dataset** (JSONL `input` + `expected`) + **runner** + **scorer**.

### 19.3 Classification eval (template for the rest)

```python
# evals/runners/run_classification.py (sketch)
def run_classification_eval():
    dataset = [json.loads(line) for line in open("evals/datasets/classification.jsonl")]
    correct = 0
    items = []
    for item in dataset:
        predicted = classify_contract(item["contract_text"])
        ok = predicted.contract_type == item["expected_type"]
        correct += int(ok)
        items.append({"expected": item["expected_type"], "predicted": predicted.contract_type, "correct": ok})
    accuracy = correct / len(dataset)
    save_report({"eval": "classification", "accuracy": accuracy, "n": len(dataset), "items": items})
    return accuracy
```

Build this first (~90 minutes). Everything else copies the pattern.

### 19.4 When the answer isn't a single label (drafting)

- **Property checks (cheap, deterministic):** mentions a liability cap? under N words? cites a precedent id? avoids banned phrases?
- **LLM-as-judge:** separate rubric prompt scores risk-addressed / preserves legal elements / clarity / precedent reflection (0–2 each). Signal, not gospel — calibrate with occasional human spot-checks.
- **Human eval:** score ~10 drafts periodically; gold standard for calibrating the judge.

### 19.5 Trajectory eval (agent-specific)

For an uncapped indemnity fixture, require the tool sequence to include at least: `search_precedents`, `check_policy`, `generate_draft_body`, `verify_schema`. Fail if missing tools, or if step count > 10. Also track efficiency (steps over time) — rising step count after a prompt change is a regression.

### 19.6 When to run

| Cadence | What |
|---|---|
| Pre-commit / PR | Fast: classification, injection, PII |
| Nightly CI | Full suite including LLM-as-judge + trajectory |
| Before Loom / zip | Full suite; paste numbers into README |

### 19.7 Target numbers (demo — quote real results, never fake)

| Eval | Target |
|---|---|
| Classification accuracy | 85%+ |
| Flag precision / recall | 80%+ / 90%+ |
| Injection false negatives | **0%** |
| Injection false positives | under 15% |
| PII redaction recall | 99%+ |
| Draft trajectory completeness | 100% |
| LLM-as-judge draft quality | avg ≥ 6/8 |

Honesty about a weaker number beats a perfect invented table.

### 19.8 Cursor workflow

Ask for feature + eval together: *"Implement the classifier node AND `evals/runners/run_classification.py` against `evals/datasets/classification.jsonl`."*

---

## 20. Web security, middleware, and DB hygiene

This is a take-home demo, not a pen-test. Reviewers check: do you understand threats, apply basic hygiene, make defensible choices, and stay honest about scope?

### 20.1 Mental model (defence in depth)

```
[ Internet ]
    → reverse proxy / TLS
    → Django middleware (CSRF, rate limit, audit, CSP)
    → views / DRF (validation, business logic)
    → ORM (parameterised SQL)
    → PostgreSQL (encryption at rest, least-privilege user)
```

Demo bar: implement the easy rings, document the rest, never claim what you didn't build.

### 20.2 What Django gives you — never disable casually

- **CSRF** — token on state-changing forms; middleware checks POST/PUT/PATCH/DELETE.
- **XSS** — template auto-escape; avoid `|safe` / `{% autoescape off %}` unless deliberate.
- **SQL injection** — ORM parameterises queries; never string-concat into `.raw()`. If raw is required: `raw("... %s", [user_input])`.
- **Clickjacking** — `XFrameOptionsMiddleware` → `X-Frame-Options: DENY`.
- **Sessions** — signed cookies keyed by `SECRET_KEY`.

### 20.3 Production settings (`settings_production.py`)

Layer on top of local settings (do **not** force HTTPS in local dev):

```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# via django-csp
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # only if Bootstrap needs it
CSP_FRAME_ANCESTORS = ("'none'",)

DEBUG = False
ALLOWED_HOSTS = ["redlineguard.example.com"]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
```

### 20.4 Middleware to add

- **Rate limit** uploads: e.g. `django-ratelimit` `@ratelimit(key="ip", rate="10/h", method="POST")` on upload.
- **Audit middleware**: on non-GET `/api/` responses, append `AuditEntry` (method, path, status, IP, actor) — feeds the hash chain.
- Keep Django's CSRF / security / XFrame middleware enabled.

### 20.5 Database

- App DB role: `SELECT/INSERT/UPDATE/DELETE` only — no DDL. Migrations run as a separate elevated role at deploy.
- Field-level encrypt sensitive columns (contract text / PII) via `django-cryptography` (or equivalent); mention Postgres TDE for disk-level encryption in production.
- All secrets via `django-environ` / `DATABASE_URL`; `.env.example` committed, `.env` gitignored.
- Backups: mention (`pg_dump` → encrypted object storage, retention) — don't build for the demo.

### 20.6 What PortSwigger will spot-check

**High:** no hardcoded secrets (`sk-…`); CSRF in `MIDDLEWARE`; `DEBUG=False` in production settings; no unbound `.raw()`; LLM client logs + rate-limits; injection defence implemented, not only described.

**Medium:** CSP; upload rate limit; 10 MB upload cap; field encryption on sensitive columns; least-privilege DB user documented.

**Low / nice:** correlation IDs in logs; health check that doesn't leak internals; dependency scanning mentioned in README.

### 20.7 README — Security posture paragraph (paste near top)

> **Security posture.** RedlineGuard is designed by a security-minded builder for a security company. Web layer: Django's built-in CSRF, XSS, and SQL-injection protections active; CSP headers strict; HTTPS enforced in production (`settings_production.py`); rate limiting on upload (10/h per IP); request size capped at 10 MB. Database: PostgreSQL with least-privilege application user; contract text and PII fields encrypted at rest; migrations run as a separate elevated user. Secrets: environment via `django-environ`; `.env.example` committed, `.env` not. LLM layer: prompt injection detection, PII redaction before cloud calls, structured output validation, ReAct draft agent with escalation tool, and audit hash chain — see `docs/security.md` and the OWASP LLM Top 10 mapping. Out of scope for the demo: end-user authentication (production would use OIDC via customer SSO), formal pen-testing, SOC 2 mapping.

That paragraph names what you did, what Django inherited, and what is out of scope.

---

## 21. Final note to future you

You already have a PRD, a visual companion doc, three diagrams, and this file. That is more design work than 90% of take-home submissions get. Now the work is to build the thing.

Practical order once coding starts:

1. Classification eval first (dataset + runner + one number in the README).
2. Triage as a fixed LangGraph chain; draft engine as the ReAct agent (Section 18).
3. Ask Cursor for feature + eval in the same prompt (Section 19.8).
4. Keep `settings_production.py` + the Security posture paragraph honest (Section 20).

If Cursor generates code that feels clever, be suspicious. Prefer boring, readable, obviously-correct code. If a reviewer at PortSwigger reads a file in your submission and cannot understand it in 60 seconds, that is a code smell.

Ship it. Get feedback. Iterate.

— End of CLAUDE.md
