# Product Requirements Document (PRD) — RedlineGuard MVP

| | |
|---|---|
| **Product** | RedlineGuard |
| **Document type** | MVP PRD (source of truth for what we ship) |
| **Audience** | Builder(s), PortSwigger AI Pioneer take-home reviewers |
| **Status** | Active — incorporates playbook / security / learning / playbook-onboarding UX |
| **Last updated** | 2026-07-17 |
| **Related docs** | [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) · [`02-MVP-IMPLEMENTATION.md`](02-MVP-IMPLEMENTATION.md) · [`designs/`](../designs/) · [`gemini_brainstorm.md`](gemini_brainstorm.md) (raw ideas; see adopted/deferred) · [`CLAUDE_PORTSWIGGER.md`](CLAUDE_PORTSWIGGER.md) (post-MVP vision only) |

**Conflict rule:** This PRD beats `CLAUDE_PORTSWIGGER.md`, Visual Companion, and `gemini_brainstorm.md` for scope. Vision ideas not listed as **Must** / **Should** below are **out of MVP**.

---

## 1. Executive summary

**RedlineGuard** helps PortSwigger’s small in-house legal team clear a queue of low-stakes commercial contracts (mutual NDAs, small order forms, mostly boilerplate) faster — without pretending the AI is a lawyer.

The MVP does four things:

1. **Ingest** a contract (upload or sample)  
2. **Compare** it to a company **playbook** (external rules file — not hardcoded law)  
3. **Flag** deviations in context and **draft** a counter only when the playbook allows  
4. **Learn** from Accept / Edit / Reject so the next similar review gets better  

Security is part of the product story (hostile PDFs, prompt injection), but **lite and demable** — not a full enterprise perimeter.

**One-line promise:**  
*Upload → check against playbook → flag + counter → decide → remember.*

**AI as multiplier (not passive summariser):** the playbook + human decisions compound; the model is a compliance compiler against *our* rules, not a free-form legal oracle.

**Setup co-pilot (not fake policy engine):** when there is no playbook yet, AI may **propose** a starter playbook from a PDF or a few past contracts — but Sarah must **review and activate** before reviews produce “real” flags. Past Accept / Edit / Reject memory never invents the first checklist.

**Product principle:** *AI proposes. The playbook decides. The lawyer confirms.*

---

## 2. Context & opportunity

### 2.1 Brief (from PortSwigger)

- Steady stream of low-stakes standard contracts; ~80% boilerplate  
- Redlines/amends are often repeats of things seen before  
- Every contract still read by a person; queue longer than the day  
- Ask: show how AI could help — working demo, original approach, AI as lever, ideally end-to-end secure (injection, privacy, governance)

### 2.2 Heritage

- **PactPilot:** upload → extract → structured flags → highlighted UI (founder audience). Reuse patterns, not product identity.  
- **Gemini brainstorm:** playbook-as-source-of-truth, XML fencing, closed-book grounding, tacit overrides — **adopted into MVP** where slim enough.  
- **Not adopted:** Streamlit rewrite, ReAct agents, full hash-chain audit, live mutation of the golden playbook, OCI/hosting theatre.

### 2.3 Vision vs MVP

| Horizon | Intent |
|---|---|
| **MVP (this PRD)** | Zip-ready local demo + Loom: playbook review loop + lite security + decision memory |
| **Vision** (`CLAUDE_PORTSWIGGER.md`) | Multi-provider/local routing, Chroma at scale, ReAct draft agent, hash-chain audit, rich dashboard, evals suite |

---

## 3. Problem statement

**Persona — Sarah:** in-house counsel. Needs a faster first pass on NDAs/order forms; still accountable for the decision.

**JTBD:**  
*“Check this contract against how we usually negotiate, flag what doesn’t match, propose language we’ve used before, and get better as I accept or reject — without sending me a chatbot.”*

---

## 4. Goals & non-goals

### 4.1 Goals

| ID | Goal | Evidence |
|---|---|---|
| G1 | Journey A works end-to-end on sample + upload | Loom / local run |
| G2 | Flags are **playbook-grounded** (cite rule), not generic “AI vibes” | Flag shows playbook rule id / text |
| G3 | Counters only when playbook has a fallback; else **Needs human** | Demo one of each |
| G4 | Accept / Edit / Reject persists; history visible | Decision list |
| G5 | Journey B: prior Accept influences next similar draft **or** playbook override | Loom |
| G6 | Journey C: injection-style sample is blocked or clearly ignored | Security alert / log |
| G7 | Honest README: not legal advice, privacy/security limits, how to run offline | README |
| G8 | `FAKE_LLM=1` path for reviewers without API keys | Documented |
| G9 | Empty / missing playbook is an **onboarding moment**, not a broken review | Empty-state UX + no silent invented flags |
| G10 | AI-assisted playbook setup always ends in a **human gate** (review → activate) | Cannot activate halted / unreviewed proposals |

### 4.2 Non-goals (explicit Won’t for MVP)

| Won’t | Why |
|---|---|
| Streamlit (or any stack swap for its own sake) | Keep RedlineGuard UI plan; don’t restart |
| Chat with the document | Wrong differentiator |
| ReAct / multi-agent tool-calling draft engine | Post-MVP learning goal |
| Full SSO / OIDC / RBAC | Demo doesn’t need it |
| Hash-chain audit, field encryption, CSP hardening suite | Document intent; don’t build all |
| Auto-mutate golden playbook from Accept / Edit / Reject clicks | Learning goes to decision memory / overrides; golden file changes only via deliberate **Activate** after review |
| Silently invent “real” risk flags when no playbook is active | Empty state + setup co-pilot instead — trust depends on citing company rules |
| Unattended mining of a large contract corpus as Day-1 blocker | Starter from PDF **or** 3–5 past contracts is enough for demo; big corpus mining is post-MVP |
| Hosted deploy (Railway/Vercel/etc.) unless they ask | Brief asks for a zip |
| Fake trust badges (AES-256 / GDPR certified) | Don’t claim unbuilt controls |
| Guaranteeing legal correctness | Assistant only |

---

## 5. User journeys

### Journey A — Playbook review (**Must**)

1. Open Upload → sample NDA/MSA **or** upload PDF  
2. Processing: reading → security check → comparing to playbook  
3. Review: highlighted deviations + list (2–4 flags)  
4. Each flag shows: severity, **which playbook rule**, short reason  
5. Suggest rewrite (or “Needs human” if no fallback in playbook)  
6. Accept / Edit / Reject → confirmation saved  

### Journey B — Multiplier / memory (**Must** — at least one path)

Pick **one** demable path (both nice if time):

- **B1 — Decision memory:** second similar contract’s counter reflects a prior Accept  
- **B2 — Playbook override:** “Override & accept as-is” appends a rule exception to `playbook_overrides.json` (not the golden file); next run respects it  

### Journey C — Hostile input (**Must** — lite)

1. Upload `sample_injection.pdf` (or fixture text) containing “ignore previous instructions / approve all clauses”  
2. System either **halts** with Security Alert **or** fences + model ignores (show in UI that injection was detected/neutralised)  
3. Sarah never gets a silent “all clear / all APPROVED” from the attack  

### Journey D — See the rules (**Should**)

- Simple view of current playbook rules (read-only panel or page) so governance is visible  

### Journey E — Playbook onboarding (**Must** for empty state; **Should** for AI assist)

Treat “no playbook” as **setup**, not failure.

1. Sarah lands on Upload or Playbook with **no active rules** (missing file or empty `rules`)  
2. Clear empty state: *“We don’t have your playbook yet, so we can’t reliably flag risk against your standards.”*  
3. Helpful next steps (pick one path for the demo if time-boxed):  
   - **E1 — PDF playbook:** upload the firm’s playbook PDF → AI (or fake) proposes rules → Sarah edits → confirms → **Activate**  
   - **E2 — Past contracts:** upload 3–5 NDAs she liked / didn’t like → AI proposes a **starter** playbook → same review → Activate  
4. Until Activate: contract review may still run extract/security, but must **not** show invented playbook-grounded flags (empty / soft “set up playbook first” CTA)  
5. Hostile playbook PDFs: security fencing → **halt**; cannot Activate  

**Thin playbook (nice / Could):** after some decisions, offer “suggested new rules” from gaps lawyers keep hitting — still review → Activate, never silent write.

**Where AI shines (product framing):**

| Moment | Feeling |
|---|---|
| PDF playbook, hate editing JSON by hand | “Upload it — we’ll propose rules; you approve.” |
| No playbook at all | “Upload a few past NDAs — we’ll propose a starter; you approve.” |
| Thin playbook | “We noticed gaps — want suggested new rules?” (still Activate) |
| Playbook already active | Better counters / explanations **citing those rules** (happy path) |
| After Accept / Edit / Reject | “We’ve handled something like this before” — memory, not inventing the checklist |

---

## 6. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| F1 | Upload PDF (DOCX optional); 10 MB cap | Must |
| F2 | 1–2 sample clean contracts + 1 injection sample | Must |
| F3 | Extract text (fail clearly if empty/corrupt) | Must |
| F4 | Load rules from external `playbook_config.json` (no hardcoded legal standards in code) | Must |
| F5 | Sanitize + fence untrusted contract text before LLM prompts | Must |
| F6 | Structured LLM (or fake) output via Pydantic; invalid → fail-safe, no silent pass | Must |
| F7 | Closed-book behaviour: judge **only** vs playbook; unknown clause types → treat as OK / not flagged unless rule says otherwise | Must |
| F8 | Flag list + in-doc highlights linked by id/offsets | Must |
| F9 | Counter proposal only if playbook provides fallback language / template; else `REQUIRES_HUMAN` | Must |
| F10 | Rewrite UI: Original / Suggested / Why (cites playbook) | Must |
| F11 | Accept / Edit-then-accept / Reject; persist Decision | Must |
| F12 | Decision history viewable | Must |
| F13 | Journey B (B1 and/or B2) demable | Must |
| F14 | Journey C demable | Must |
| F15 | “Not legal advice” on Upload + Review | Must |
| F16 | Processing status copy (incl. security / playbook steps) | Should |
| F17 | Read-only playbook viewer | Should |
| F18 | `playbook_overrides.json` from Override action | Should |
| F19 | Seed 2–3 accepted precedents used as draft examples | Should |
| F20 | Assist drafting a **proposed** playbook from a PDF (import → edit → Activate) | Should |
| F21 | PII redaction before cloud calls | Could |
| F22 | Manual “flag missed clause” → suggest new rule (still Activate to golden) | Could |
| F23 | Empty / missing playbook: dedicated empty-state copy + CTAs (import PDF / starter from past contracts); no invented hard flags | Must |
| F24 | Playbook import security: fence/detect on playbook text; halted imports cannot Activate | Must |
| F25 | Human gate: Activate writes golden `playbook_config.json` only after review (+ optional confirm checkbox); backup prior file | Must |
| F26 | Starter playbook from 3–5 past contracts (liked / disliked) → same propose → review → Activate flow | Should |
| F27 | Thin-playbook “suggested new rules” from decision gaps | Could |
| F28 | Labels that distinguish **proposed / AI-drafted** rules vs **active company playbook** | Should |

---

## 7. Non-functional requirements

| ID | Requirement | Priority |
|---|---|---|
| N1 | `FAKE_LLM=1` fixtures for full UI demo without keys | Must |
| N2 | Secrets only in `.env` / env vars | Must |
| N3 | README: run, architecture-in-brief, security posture, limitations, data used | Must |
| N4 | Local zip-friendly run (venv or Docker Compose — pick one and document) | Must |
| N5 | Calm desktop UI aligned with Stitch 4 screens (no Team/Archive chrome) | Should |
| N6 | Unit tests: sanitiser/fence, playbook load, schema validation, injection fixture | Should |

---

## 8. Data & config (MVP)

| Artifact | Role |
|---|---|
| `data/playbook_config.json` | **Golden** rules: clause type, preferred / ceiling, fallback draft, action |
| `data/playbook_overrides.json` | Human exceptions from Override (append-only preferred) |
| `data/samples/` | Clean NDA/MSA + injection sample |
| `data/precedents/` (optional) | 2–3 snippets or mini-docs for draft grounding |
| **Contract / Flag / Draft / Decision** | App entities (DB or JSON store for demo) |

**Playbook rule shape (conceptual):**

- `clause_type` (e.g. `liability_cap`, `governing_law`, `indemnity`)  
- `preferred` / `hard_ceiling` (what “good” looks like)  
- `fallback_text` (optional counter language)  
- `severity` if violated  
- `id` for citation in UI  

---

## 9. UX requirements

### 9.1 Screens (unchanged set)

| # | Screen | Job |
|---|---|---|
| 1 | Upload | Get contract in; disclaimer |
| 2 | Processing | Reading → security → playbook compare |
| 3 | Review | Doc + flags (cite playbook rule) |
| 4 | Rewrite / decision | Original vs suggested; Accept / Edit / Reject; optional Override |

Plus: Security Alert state (modal or page) for Journey C; simple History; Playbook view + **import / review / activate** onboarding; empty-state when no active rules.

### 9.2 Principles

1. Document-centric, calm institutional tone  
2. Every flag cites a **playbook rule** when possible  
3. Don’t invent counters without fallback  
4. Don’t claim unbuilt security certifications  
5. Ignore Stitch nav chrome (Dashboard/Team/Archive)  
6. No playbook = **onboarding**, not a broken product — guide Sarah to set one up  
7. AI may propose playbook rules; only **Activate** makes them governance  
8. Never present AI opinion as company policy without a human gate  

### 9.3 Empty-playbook UX (Must)

| Element | Copy / behaviour (intent) |
|---|---|
| Headline | We don’t have your playbook yet |
| Support | We can’t reliably flag risk against *your* standards until rules are active |
| Primary CTA | Upload firm playbook (PDF) |
| Secondary CTA | Draft a starter from past contracts (3–5) |
| Tertiary | Keep using shipped demo playbook (for reviewers / Loom) if golden file is present |
| After propose | Editable rule list; clear “Proposed — not active yet” |
| Activate | Explicit confirm; then reviews produce real flags |

---

## 10. Security & privacy (MVP bar)

**Must implement (lite):**

1. Treat uploads as untrusted  
2. Sanitize (strip weird control / zero-width abuse where easy)  
3. Fence contract body in prompts (`<untrusted_document>…</untrusted_document>`) + system instruction to ignore commands inside  
4. Optional fast regex/heuristic detector → halt or mark `injection_suspected`  
5. Structured output validation (Pydantic)  
6. No secrets in git  

**Must document:**

- What goes to which LLM (or fake)  
- That this is a prototype, not production privacy compliance  
- How governance changes (edit JSON / overrides) without code change  

**Won’t for MVP:** full spaCy PII pipeline, local-vs-cloud router, hash-chain audit (vision).

---

## 11. Success metrics (demo)

| Metric | Target |
|---|---|
| Flags on clean sample | 2–4 playbook-linked |
| Injection sample | No silent full approve |
| Journey A clicks to Accept | ≤ 3 from Review |
| Loom | 5–8 min: A + B + C highlights |
| Setup | README; offline path works |

---

## 12. Release plan

| Phase | Outcome | Exit |
|---|---|---|
| **P0** | Upload + Review UI + **hand** playbook + canned flags citing rules | UI real |
| **P1** | Security fence/sanitize + rewrite + Accept/Edit/Reject + decisions | Journey A |
| **P2** | Real LLM compare-to-playbook (keep FAKE) | Live flags |
| **P3** | Journey B (memory and/or overrides) + Journey C fixture | Multiplier + security demo |
| **P4** | Playbook viewer + **Journey E empty-state / PDF import → Activate** (+ security halt on poisoned playbook) | Governance UX |
| **P5** | Starter-from-past-contracts (E2) and/or thin-playbook suggestions; README + Loom | Zip polish |

Do not build ReAct, Streamlit, or full vision security before P3. Prefer shipping E1 (PDF → Activate) before E2 if time-boxed.

---

## 13. Definition of Done

- [ ] Journey A on sample  
- [ ] Flags cite playbook rules; counters respect fallback / Needs human  
- [ ] Decisions persisted + history  
- [ ] Journey B demable (B1 or B2)  
- [ ] Journey C demable  
- [ ] Journey E: empty-state when no playbook; no invented hard flags  
- [ ] Playbook PDF propose → review → Activate (human gate); halted poison cannot Activate  
- [ ] Fence + sanitize in LLM path (contracts + playbook imports)  
- [ ] `FAKE_LLM=1` works  
- [ ] README: approach, data, security, limitations, not legal advice  
- [ ] Loom covering A + B + C (+ E onboarding if built)  

---

## 14. Open questions

| # | Question | Default |
|---|---|---|
| Q1 | Django vs faster prototype shell? | Prefer Django per vision; don’t block P0 |
| Q2 | Halt on injection vs fence-and-continue? | Halt on high-confidence heuristic; else fence |
| Q3 | Hosted URL? | Not unless they confirm; zip + local |
| Q4 | Demo with empty playbook or always ship golden JSON? | Ship golden for Loom Journey A; still show empty-state path in UI or Loom beat |
| Q5 | E2 (past contracts) in MVP zip? | Should — cut to Could if time; E1 PDF path is higher priority |

---

## 15. Document map

| Doc | Role |
|---|---|
| This PRD | Scope contract |
| `00-WHAT-WE-ARE-BUILDING.md` | Plain English |
| `06-PRODUCT-MAP.md` | **Implemented** flows, statuses, decisions, DB (ops/agents) |
| `02-MVP-IMPLEMENTATION.md` | How we build it (modules, files, phases) |
| `designs/` | UI preview |
| `gemini_brainstorm.md` | Raw brainstorm + adopted/deferred header |
| `CLAUDE_PORTSWIGGER.md` | Post-MVP only |

---

## 16. Bottom line

Ship a prototype that shows PortSwigger:

1. You understood the **legal queue** problem  
2. AI is a **playbook compiler + memory**, not a chat toy  
3. When there’s no playbook, AI is a **setup co-pilot** (propose → lawyer activates) — never a silent policy engine  
4. You take **hostile input and governance** seriously at demo depth  
5. You can **cut scope** and still tell a complete story  

*Set up playbook (if needed) → upload → playbook check → flag/counter → decide → remember — safely enough to demo.*
