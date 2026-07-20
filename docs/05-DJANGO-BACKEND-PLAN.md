# Django backend plan — what we will build

**Audience:** Implementers of the RedlineGuard MVP app.  
**Status:** Design intent (not implemented yet).  
**Foundation:** Port behaviour from [`04-SCRATCH-FOUNDATION.md`](04-SCRATCH-FOUNDATION.md).  
**Product authority:** [`01-PRD-MVP.md`](01-PRD-MVP.md) · stack notes in [`02-MVP-IMPLEMENTATION.md`](02-MVP-IMPLEMENTATION.md).

---

## 1. Goal

Turn the scratch CLI pipeline into a **Django modular monolith** Sarah can use:

**Upload → process → review flags → accept/edit/reject rewrite → remember**  
(+ security halt screen; + history).

Scratch stays the behavioural oracle. Django adds: UI, ORM persistence, HTTP API shapes, and a single `ReviewPipeline` service.

---

## 2. Architecture choice

**Modular monolith** — one Django process, one SQLite DB, local Chroma.

Not microservices (wrong size for a GitHub/zip take-home — see [`13-HANDOFF.md`](13-HANDOFF.md)).

```
HTTP (templates + thin JSON API)
    → Application services (ReviewPipeline, DecisionService)
        → Domain rules (playbook, finding, decision)
            → Adapters (pdfplumber, security, Fake/LLM draft, Chroma, JSON playbook, ORM)
```

**Clean-architecture rules:**

- Views stay thin; no pipeline logic in templates  
- Playbook golden file never mutated by Accept  
- Learning = ORM `Decision` + Chroma write  
- Security HALT short-circuits; no memory pollution  
- Strategy ports: `Embedder`, `DraftEngine`, `LlmClient` (`FAKE_*` for offline)

---

## 3. App layout

```
redlineguard/
├── manage.py
├── config/                 # settings, urls, wsgi
├── apps/
│   ├── contracts/          # upload, extract, Contract model, triage fields
│   ├── security/           # sanitize, fence, detect_injection (from scratch)
│   ├── review/             # playbook compare, findings, drafts, pipeline
│   ├── learning/           # Chroma DecisionStore adapter, MiniLM/Hash embedder
│   ├── decisions/          # Accept/Edit/Reject, history, optional overrides
│   └── core/               # shared DTOs, FAKE_LLM client later
├── data/                   # playbook_config.json, samples, vector_memory/
├── templates/              # Upload, Processing, Review, Rewrite, Alert, History
├── static/
└── scratch/                # keep as regression lab
```

| App | Scratch source |
|---|---|
| `contracts` | poc01 + poc03 |
| `security` | poc02 |
| `review` | poc04 + poc07 engine + pipeline |
| `learning` | poc06 |
| `decisions` | decide_cli + history |

---

## 4. Database models (SQLite via Django ORM)

Vectors stay in **Chroma**, not ORM.

| Model | Purpose |
|---|---|
| `Contract` | Uploaded/sample file; extracted text; `quality`; `status` (`uploaded` → `processing` → `ready` \| `halted` \| `failed`); triage `kind` / `stakes` |
| `ReviewRun` | One analysis pass; risk score; playbook version stamp; timestamps |
| `SecurityEvent` | halt bool, matches JSON, summary (Journey C) |
| `Finding` | rule_id, status (`FLAGGED` / `REQUIRES_HUMAN`), severity, reason, char offsets for highlight |
| `Draft` | draft_text, draft_source, precedent_ids, rationale |
| `Decision` | action accept/edit/reject, final_text, reasoning, chroma_id FK-ish |
| `PlaybookOverride` *(Should)* | exception rows; also sync `playbook_overrides.json` |
| `AuditLog` *(thin)* | optional who/when for demo honesty |

**Relationships:** `Contract` 1→N `ReviewRun` → N `Finding` → 0..1 `Draft` → N `Decision`.

---

## 5. API contracts (freeze with UI)

Even if the primary UX is server-rendered, keep JSON shapes stable for polling and Loom clarity.

| Method | Path | Job |
|---|---|---|
| POST | `/api/contracts/` | Upload multipart or `{ "sample_id" }` |
| GET | `/api/contracts/<uuid>/` | Status + meta |
| POST | `/api/contracts/<uuid>/analyze/` | Run pipeline (or auto on upload) |
| GET | `/api/contracts/<uuid>/review/` | Findings + drafts + document text + security |
| POST | `/api/findings/<uuid>/decide/` | `{ action, final_text?, reasoning? }` → ORM + Chroma |
| GET | `/api/decisions/` | History list |
| GET | `/api/playbook/` | Read-only rules (+ overrides) |
| POST | `/api/playbook/overrides/` | Journey B2 *(optional Should)* |

**Review payload sketch:**

```json
{
  "contract_id": "...",
  "status": "ready",
  "security": { "halt": false, "summary": "..." },
  "triage": { "kind": "nda", "stakes": "routine_queue" },
  "risk_score": 42,
  "findings": [
    {
      "id": "...",
      "rule_id": "uncapped_or_broad_indemnity",
      "status": "FLAGGED",
      "severity": "high",
      "reason": "...",
      "offsets": { "start": 0, "end": 0 },
      "draft": {
        "text": "...",
        "source": "memory_precedent",
        "rationale": "..."
      }
    }
  ]
}
```

Pydantic (or serializers) at the boundary — fail closed, no silent junk.

---

## 6. Pages / URLs (Stitch journeys)

| URL | Screen |
|---|---|
| `/` | Upload (sample + file) |
| `/contracts/<uuid>/processing/` | Processing |
| `/contracts/<uuid>/review/` | Review (flags + highlights) |
| `/contracts/<uuid>/rewrite/<finding_id>/` | Rewrite + Accept/Edit/Reject |
| `/security/<uuid>/` | Security alert (halt) |
| `/history/` | Decision history |
| `/playbook/` | Active playbook **or** empty-state onboarding |
| `/playbook/import/` | Upload firm playbook PDF (E1) |
| `/playbook/import/<uuid>/` | Review / edit proposed rules |
| `/playbook/import/<uuid>/activate/` | Human gate → write golden file |
| `/playbook/starter/` *(Should)* | Upload 3–5 past contracts (E2) → propose starter |

Designs: [`designs/`](../designs/) — ignore Team/Archive chrome. Empty playbook copy per PRD §9.3.

---

## 7. Core services

| Service | Behaviour |
|---|---|
| `ReviewPipeline.run(contract_id)` | extract → security → triage → playbook → retrieve → draft → persist run |
| `SecurityGate` | wrap scratch detect; on halt persist `SecurityEvent` and stop |
| `PlaybookService` | load `playbook_config.json` + merge overrides; expose `empty` when no rules |
| `PlaybookImportService` | extract PDF → playbook security gate → propose rules (Fake/LLM) → edit → **Activate** (backup + write golden) |
| `PlaybookStarterService` *(Should)* | from 3–5 past contracts → propose starter → same Activate path |
| `VectorMemoryPort` | Chroma add/search; Hash vs MiniLM via env — **does not** invent first checklist |
| `DraftEngine` | Fake first; LLM later behind same interface |
| `DecisionService` | Accept/Edit/Reject → ORM transaction then Chroma |

**Empty playbook:** pipeline may extract + security-check, but must not invent playbook-grounded findings — surface setup CTA instead.

**Sync first.** Optional: mark `processing` and finish in `transaction.on_commit` — no Celery for MVP.

---

## 8. Config / env

| Variable | Meaning |
|---|---|
| `FAKE_EMBED=0` | MiniLM (default for `runserver` / demos) |
| `FAKE_EMBED=1` | Hash embeddings (tests / offline; auto when `manage.py test`) |
| `FAKE_LLM=1` | Fixture structured review / draft *(when LLM path lands)* |
| `DATABASE_URL` / default SQLite | Local demo |
| `CHROMA_PATH` | Default `data/vector_memory/` |

`.env.example` only — never commit secrets.

---

## 9. Build order (MVP)

1. Django project skeleton + apps + SQLite  
2. `Contract` upload + extract (call scratch extract)  
3. Security gate + halt template  
4. Playbook compare → `Finding` rows + Review page  
5. `Draft` + Rewrite page + `DecisionService` (ORM history)  
6. Wire Chroma retrieve into pipeline (prove Journey B)  
7. **Journey E:** empty-state + PDF import → security → propose → edit → Activate (+ poisoned playbook halt)  
8. Polish: Processing poll, History, README offline path  
9. Optional: E2 starter from past contracts; `FAKE_LLM` / real LLM draft; overrides (B2); thin-playbook suggestions  

Each step should stay demable on Loom.

---

## 10. Explicit non-goals (backend)

From PRD Won’t list — do not sneak in:

- Microservices / Celery / Redis  
- Auto-mutate golden `playbook_config.json` from Accept / Edit / Reject (Activate after review is **in** scope)  
- Silent invented findings when playbook is empty  
- ReAct / multi-agent draft graph  
- SSO / full RBAC  
- Hosted deploy theatre / Docker / `.exe` packaging (see [`13-HANDOFF.md`](13-HANDOFF.md))
- Claiming unbuilt crypto/compliance badges  

---

## 11. Definition of done (Django MVP)

- [ ] Journey A: sample/upload → flags citing playbook → Accept  
- [ ] Journey B: second similar contract shows `draft_source=memory_precedent` (or override path)  
- [ ] Journey C: malicious/injection sample → security alert, no silent approve, no Chroma write  
- [ ] Journey E: empty playbook → onboarding CTAs; no invented hard flags  
- [ ] Playbook PDF propose → Activate; halted poison cannot Activate  
- [ ] History shows past decisions  
- [ ] Scratch pytest still green; Django can call the same security/playbook/memory logic  
- [ ] README: not legal advice, how to run with `FAKE_*`  

---

## 12. Related docs

| Doc | Role |
|---|---|
| [`04-SCRATCH-FOUNDATION.md`](04-SCRATCH-FOUNDATION.md) | What already works to port |
| [`01-PRD-MVP.md`](01-PRD-MVP.md) | Must/Should/Won’t (incl. Journey E / setup co-pilot) |
| [`02-MVP-IMPLEMENTATION.md`](02-MVP-IMPLEMENTATION.md) | Earlier implementation sketch |
| [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) | Plain English product |
| [`scratch/README.md`](../scratch/README.md) | How to re-prove seams |
