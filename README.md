# RedlineGuard

Take-home prototype for PortSwigger’s AI Pioneer brief: **playbook-grounded** first-pass contract review for in-house legal — with lite security and decision memory.

**One-line promise:** Set up playbook (if needed) → upload → check playbook → flag/counter → decide → remember.

**Principle:** AI proposes. The playbook decides. The lawyer confirms.

---

## How PortSwigger should try this

| | |
|---|---|
| **Delivery** | Clone from GitHub (or unzip the same tree). **No hosted deploy.** No `.exe`. **No Docker** in this MVP. |
| **Samples** | **Included** — Quick demos + playbook PDFs + golden `playbook_config.json` ship in the repo. |
| **First run** | Offline by default: Fake LLM + optional fast hash embeddings. No API keys. |
| **Accounts** | Demo users after `bootstrap_demo_users` (passwords are for the demo only). |

Full rationale: [`docs/13-HANDOFF.md`](docs/13-HANDOFF.md).

### Evaluator path (~10 minutes)

```bash
git clone https://github.com/New-Sheep/RedlineGuard.git
cd RedlineGuard

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
# In .env (recommended for first try): FAKE_LLM=1 and FAKE_EMBED=1

python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents
python manage.py runserver
```

Open http://127.0.0.1:8000/ → sign in **`lawyer` / `lawyer-demo-2026`** → **Upload** → use **Quick demos** (Sample with issues / Short NDA / Hostile sample).

Admin: **`admin` / `admin-demo-2026`**. Set `REQUIRE_AUTH=0` only for local scripts; leave auth on for demos.

**Tip:** `FAKE_EMBED=1` skips the MiniLM download so cold machines stay fast. For richer memory similarity later, set `FAKE_EMBED=0` (model warms at server start).

---

## Approach (for reviewers)

| Idea | What it means here |
|------|--------------------|
| Playbook compiler | Flags cite company rules in `playbook_config.json` — not generic “AI vibes” |
| Setup co-pilot | PDF import **or** starter from 3–5 past contracts proposes rules; Sarah **Activates**. Empty playbook = onboarding |
| Decision memory (B1 / Sprint 5) | Clause-excerpt Chroma (`django_decisions_v2`); Memory page; provenance; Reject=Avoid; distance gate |
| Override (B2) | “Override & accept as-is” appends to `playbook_overrides.json` — **never** rewrites the golden playbook |
| Security | Uploads untrusted; sanitize + injection halt; adjudicator for ambiguous cues; **10 MB** upload cap |
| Ingest | PDF / **DOCX** / TXT |
| Live progress | Analyze runs in the background; Processing page shows steps (reading → security → playbook → draft) |
| LLM drafts | Needs-human flags get suggested counters via `FAKE_LLM` (default Fake) or optional real API |
| UI | Django templates — no React dependency |

## Start here (read in order)

1. **[Handoff](docs/13-HANDOFF.md)** — clone / samples / why not Docker or deploy  
2. **[What are we building?](docs/00-WHAT-WE-ARE-BUILDING.md)** — plain English  
3. **[Product map](docs/06-PRODUCT-MAP.md)** — flows, statuses, decisions, DB  
4. **[MVP PRD](docs/01-PRD-MVP.md)** — Must / Should / Could / Won’t  
5. **[MVP audit checkpoint](docs/07-MVP-AUDIT-CHECKPOINT.md)** — shipped vs PRD  
6. **[Compare algorithm audit](docs/08-COMPARE-ALGORITHM-AUDIT.md)** — L0+L1+L2  
7. **[Lawyer wishlist](docs/10-LAWYER-WISHLIST-SPRINTS.md)** · **[Lawyer API](docs/11-LAWYER-API.md)**  
8. **[MVP Implementation](docs/02-MVP-IMPLEMENTATION.md)** — stack, modules, build order  
9. **[Scratch foundation](docs/04-SCRATCH-FOUNDATION.md)** — CLI lab that seeded Django  
10. **[Django backend plan](docs/05-DJANGO-BACKEND-PLAN.md)** — modular monolith  
11. **[Stitch designs](designs/README.md)** — four screens (ignore Team/Archive chrome)  

## Demo samples (use these first)

Committed under `data/scratch_corpus/`. Also exposed as **Quick demos** on Upload.

| Sample | Journey |
|--------|---------|
| **Demo — clean contract** / Sample with issues | A — Review → rewrite → Accept |
| **Demo — short form** / Short NDA | A — quicker path |
| **Demo — hostile / injection** / Hostile sample | C — Security alert |

Playbook PDFs: `data/playbook_corpus/`. **Text-based PDFs only** for uploads; scanned image PDFs fail with a clear message — use a Quick demo first.

## Optional: real LLM (not required)

LLM drafts default to **Fake** (`FAKE_LLM=1`). For **local Ollama**:

```bash
# in .env:
# FAKE_LLM=0
# OLLAMA_HOST=http://127.0.0.1:11434
# OLLAMA_MODEL=<model you pulled, e.g. llama3.1:8b>

python manage.py check_ollama
python manage.py runserver
```

`.env` is loaded via `python-dotenv`. If Ollama is down or returns bad JSON, drafts fall back to Fake.

| `LLM_PROVIDER` | Backend |
|----------------|---------|
| `auto` (default) | First of NVIDIA → DeepSeek → Moonshot keys, else Ollama |
| `nvidia` / `deepseek` / `moonshot` | OpenAI-compatible cloud HTTP |
| `ollama` | Local Ollama (`OLLAMA_*`) |
| `http` | Generic `LLM_API_KEY` + `LLM_BASE_URL` + `LLM_MODEL` |

**Magical LLM agents** (`FAKE_LLM=0`): playbook propose, rewrite co-pilot, memory explain, decision brief, plain-English gloss, scoped ask. Stretch: `LLM_GAP_SUGGEST=1`, `LLM_DISCOVER=1`. Smoke: `python manage.py check_llm --draft`.

**L2 judge:** with `FAKE_LLM=0`, compare runs a closed-book pass on each flag. Set `LLM_JUDGE=0` to skip.

**Security:** CSRF on mutating APIs; session roles; admin lab `/lab/` (confirm `RESET`); audit is append-only. Explainability: `/trust/`. Evals: `python -m evals.runners.run_all`.

### Contracts

- Analyze → security → playbook compare → draft → **Review** (document + flags)
- **Rewrite:** Accept / Edit / Reject / **Override & accept as-is**
- **History** at `/history/` · **Memory** at `/memory/` (precedents, Unlearn, overrides)

### Playbook (no JSON for lawyers)

1. `/playbook/` — **Active company playbook** (or empty-state CTAs)  
2. **Import playbook PDF** (`/playbook/import/`) → Sample Playbook1.pdf → edit → **Activate**  
3. **Starter from past contracts** (`/playbook/starter/`) → pick/upload 3–5 NDAs → Activate  
4. Poisoned Sample Playbook2 / hostile starter text → **halted**, cannot Activate  
5. Proposed rules always show **Proposed — not active yet** until Activate  

### Smoke checklist (zip / Loom)

- [ ] Journey **A:** demo clean sample → flags cite rules → Accept  
- [ ] Journey **B:** seed precedents *or* prior Accept → memory draft / Override  
- [ ] Journey **C:** hostile sample → Security alert  
- [ ] Journey **E1:** playbook PDF import → Activate  
- [ ] Journey **E2:** `/playbook/starter/` with 3 samples → Activate  
- [ ] Offline: `FAKE_LLM=1` + `FAKE_EMBED=1` still runs  

### Governance cheat-sheet

| Action | Writes |
|--------|--------|
| Activate playbook | `data/playbook_config.json` (backup `.bak`) |
| Override & accept as-is | `data/playbook_overrides.json` (append-only) |
| Accept / Edit | ORM Decision + Chroma (`django_decisions_v2`, clause excerpt) |
| Reject | ORM Decision + Chroma Avoid signal |
| Unlearn | Deletes Chroma id; `Decision.memory_active=False` |

### Tests

```bash
# Fast offline tests (hash embeddings — also auto when running manage.py test)
set FAKE_EMBED=1
python manage.py test apps.contracts apps.review apps.security apps.decisions apps.learning
```

## 5-minute Loom beat sheet

1. **A:** Upload `Demo — clean contract` → show 2+ flags citing rules → Review rewrite → Accept → **Memory**  
2. **B:** Re-analyze similar text → Rewrite shows **provenance** **or** Override one rule → that rule no longer flags. Tip: `python manage.py seed_precedents` for a cold start.  
3. **C:** Upload `Demo — hostile / injection` → Security alert  
4. **E:** Empty playbook CTA → **Import PDF** *or* **Starter from past contracts** → **Proposed — not active yet** → Activate  
5. **(Optional):** Reject → Avoid on Memory; Unlearn; `/api/memory/`  

## Smoke evals

```bash
set FAKE_LLM=1
python -m evals.runners.run_smoke
```

Writes `evals/reports/latest.json`. Typical offline result: **4/4** (hard injection hold, ambiguous peer proceed, California flag, clean UK).

## Security posture (honest)

- Heuristic injection detection + sanitize; halt on high-confidence hits  
- Contract path treats Gemini chat-export chrome as hostile; playbook import does not (real playbooks often come from Gemini)  
- Prototype only — not production privacy/compliance; no secrets in git  
- Offline path: `FAKE_EMBED=1` (hash embeddings); richer default is MiniLM (`FAKE_EMBED=0`). Playbook flags = L0 regex + L1 local semantic (`SEMANTIC_COMPARE=1`); no cloud LLM required for flags  

## Limitations

- Not legal advice  
- Heuristic playbook matching (not full LLM legal reasoning yet)  
- Overrides suppress whole rules (coarse)  
- Local SQLite + local Chroma  
- Not a production deploy — local demo only  

## Reference only (not MVP authority)

- `docs/03-SCRATCH-DRYRUN.md`, `docs/gemini_brainstorm.md`, `docs/CLAUDE_PORTSWIGGER.md`

**Conflict rule:** PRD + README + [`docs/13-HANDOFF.md`](docs/13-HANDOFF.md) win over vision docs.
