# Scratch foundation — what we built (backend seed)

**Audience:** Anyone starting the Django backend.  
**Status:** Proven in the scratch lab (CLI + pytest + real PDFs).  
**Authority:** Product scope still follows [`01-PRD-MVP.md`](01-PRD-MVP.md). This doc is the **technical inventory** of working seams to port.

Commands live in [`scratch/README.md`](../scratch/README.md). Lab notes: [`03-SCRATCH-DRYRUN.md`](03-SCRATCH-DRYRUN.md).

---

## 1. Why scratch existed

Before Django UI, we proved each RedlineGuard seam against real contracts:

- Extract + quality gate  
- Security halt on hostile PDFs  
- Playbook-grounded findings (not vibes)  
- Vector memory of Accept/Edit/Reject  
- Draft from memory or playbook fallback (no inventing)  
- Learning across runs with **real MiniLM** embeddings  

Django should **wrap and persist** these seams — not reinvent them.

---

## 2. Pipeline (the product loop, already working)

```
PDF/txt
  → 01 Extract (+ quality)
  → 02 Security (sanitize / fence / injection → HALT?)
  → 03 Triage (kind / stakes)
  → 04 Playbook compare (FLAGGED | REQUIRES_HUMAN)
  → 05 Memory retrieve (Chroma precedents)
  → 06 Draft (FakeDraftEngine)
  → Decide CLI (Accept/Edit/Reject → Chroma write-back)
```

Orchestrator: [`scratch/05_dry_run_cli.py`](../scratch/05_dry_run_cli.py)  
Artifacts: `scratch/out/<stem>/latest/` (`01_` … `06_`, `journey.md`)

**Hard rules proven in scratch:**

| Rule | Behaviour |
|---|---|
| Security HALT | Skip triage/playbook/memory/draft; **never** write Chroma |
| Poor quality | Skip later steps (e.g. Tippett scan) |
| Golden playbook | `data/playbook_config.json` is **never** auto-updated |
| Learning | Only via explicit Accept/Edit/Reject (or seed) into Chroma |
| Draft closed-book | Memory accept/edit → else playbook fallback → else `none` |

---

## 3. Package map (port these)

| Package | Responsibility | Port to Django |
|---|---|---|
| [`scratch/poc01_extract/`](../scratch/poc01_extract/) | pdfplumber extract, page/char counts, `quality` ok/poor | `apps/contracts` |
| [`scratch/poc02_security/`](../scratch/poc02_security/) | sanitize, fence, injection detect (EN + multilingual + Gemini chrome + stuffing) | `apps/security` |
| [`scratch/poc03_triage/`](../scratch/poc03_triage/) | kind / stakes / major terms heuristics | `apps/contracts` or review summary |
| [`scratch/poc04_playbook/`](../scratch/poc04_playbook/) | load JSON rules, regex/heuristic compare, findings | `apps/review` |
| [`scratch/poc06_memory/`](../scratch/poc06_memory/) | Embedder + Chroma `DecisionStore`, DecisionRecord | `apps/learning` |
| [`scratch/poc07_draft/`](../scratch/poc07_draft/) | `DraftEngine` / `FakeDraftEngine`, `decide_cli` | `apps/review` + `apps/decisions` |
| `05_dry_run_cli.py` | Full pipeline orchestration | `ReviewPipeline` service |

Shared I/O: [`scratch/_io.py`](../scratch/_io.py) (corpus paths, run dirs, banners).

---

## 4. Key types & interfaces (keep stable)

### Decision memory (`poc06_memory`)

- `DecisionRecord`: `id`, `clause_text`, `decision` (`accept`/`edit`/`reject`), `final_text`, `playbook_rule_id?`, `contract_id`, `reasoning?`, `created_at`
- `DecisionStore.add_decision` / `search_precedents(query, top_k, playbook_rule_id?)`
- Persist dir: `data/vector_memory/` (gitignored)
- Prefer same `playbook_rule_id` when filtering; cosine space in Chroma

### Embeddings

| Mode | Env / flag | Backend |
|---|---|---|
| Offline / pytest | `FAKE_EMBED=1` (default) | `HashEmbedder` |
| Real semantic | `FAKE_EMBED=0` or `--real-embed` | MiniLM `all-MiniLM-L6-v2` via `sentence-transformers` |

**Do not mix** hash and MiniLM vectors in one collection — reset when switching.

### Draft (`poc07_draft`)

- `DraftResult`: `playbook_rule_id`, `finding_status`, `draft_text`, `draft_source`, `precedent_ids`, `rationale`
- `draft_source`: `memory_precedent` | `playbook_fallback` | `none`
- `FakeDraftEngine` implements `DraftEngine` — swap for `LlmDraftEngine` later without changing the pipeline

### Playbook findings (`poc04`)

- Status: `APPROVED` | `FLAGGED` | `REQUIRES_HUMAN`
- Fields: `playbook_rule_id`, `deviation_reason`, `suggested_counter_proposal?`, `severity`

---

## 5. Data on disk (not Django yet)

| Path | Role |
|---|---|
| `data/playbook_config.json` | Golden governance rules (hand-edited only) |
| `data/vector_memory/` | Chroma persistent store |
| `data/scratch_corpus/` | Clean + cyber T&Cs PDFs for dry-runs |
| `data/malicious_corpus/` | Injection PDFs (contracts 1–13); all should HALT |
| `scratch/out/` | Per-run artifacts (gitignored) |

---

## 6. Demo scripts (regression / Loom evidence)

| Script | Proves |
|---|---|
| `scratch/run_memory_learning_demo.py` | Seed → retrieve; malicious never pollutes memory |
| `scratch/run_draft_learning_demo.py` | Accept → next draft `memory_precedent` (hash embed) |
| `scratch/run_real_minilm_cyber_learning.py` | MiniLM + cyber Accepts → second-pass learning |
| `scratch/run_malicious_report.py` | All malicious PDFs HALT |

**Verified outcomes (as of last real MiniLM pass):**

- `pytest scratch/` green with `FAKE_EMBED=1`  
- Malicious corpus **1–13** HALT  
- After cyber Accepts into collection `cyber_minilm`, corpus re-run showed **memory_precedent** on multiple docs (learning visible)  
- Playbook JSON untouched throughout  

---

## 7. Known limits (honest — Django must not pretend otherwise)

- Draft text is still **FakeDraftEngine** (no network LLM writer yet)  
- Playbook compare is **heuristic/regex**, not full LLM clause review  
- Triage labels many cyber docs as `kind=unknown`  
- Some playbook rules (e.g. `equity_control_cap`) over-fire on security addenda  
- No Django UI, no ORM persistence of runs/decisions yet  
- Chroma is local-only; not multi-user  

---

## 8. Porting checklist (foundation → backend)

When building Django, prefer **lift-and-call** over rewrite:

1. [ ] Call `sanitize` / `fence` / `detect_injection` from `apps/security`  
2. [ ] Call extract + quality from `apps/contracts`  
3. [ ] Load playbook via same JSON schema; keep golden file immutable from UI  
4. [ ] Persist findings/drafts/decisions in SQLite; still write Accepts to Chroma  
5. [ ] Keep `DraftEngine` / `Embedder` strategy pattern  
6. [ ] Same HALT short-circuit in `ReviewPipeline`  
7. [ ] Keep `FAKE_EMBED` / future `FAKE_LLM` for offline reviewers  
8. [ ] Leave scratch lab runnable as the behavioural oracle  

---

## 9. Reading order from here

1. This file (foundation)  
2. [`05-DJANGO-BACKEND-PLAN.md`](05-DJANGO-BACKEND-PLAN.md) — what we will build next  
3. [`02-MVP-IMPLEMENTATION.md`](02-MVP-IMPLEMENTATION.md) — stack + build order  
4. [`scratch/README.md`](../scratch/README.md) — how to re-run proofs  
