# RedlineGuard

Take-home prototype for PortSwigger’s AI Pioneer brief: **playbook-grounded** first-pass contract review for in-house legal — with generative AI drafts, MiniLM decision memory, lite security.

**One-line promise:** Set up playbook (if needed) → upload → check playbook → flag/counter → decide → remember.

**Principle:** AI proposes. The playbook decides. The lawyer confirms.

---

## What’s in this zip / clone

| Included | Not included (by design) |
|----------|---------------------------|
| Full Django app + templates + static CSS | `.venv`, `.env`, **API keys** (you add yours) |
| Sample contracts, playbook PDFs, golden `playbook_config.json` | Runtime DB (`db.sqlite3`), Chroma under `data/vector_memory/` |
| `.env.example`, this README, [`docs/13-HANDOFF.md`](docs/13-HANDOFF.md) | Docker / hosted URL / Windows `.exe` |
| Wiring for **NVIDIA / Ollama / other OpenAI-compatible LLMs** + **MiniLM** embeddings | Production hardening claims |

**Requirements:** Python **3.11+**, plus **one** LLM backend (NVIDIA API key *or* local Ollama). First run may download MiniLM once (~90 MB). Prefer unzip or clone; run locally only.

**Same tree on GitHub:** https://github.com/New-Sheep/RedlineGuard

---

## How PortSwigger should try this

| | |
|---|---|
| **Delivery** | Unzip this package **or** clone from GitHub. **No hosted deploy.** |
| **Intended AI path** | Real LLM (`FAKE_LLM=0`) + MiniLM memory (`FAKE_EMBED=0`). This is the product. |
| **What you bring** | An **NVIDIA API key** (recommended) *or* **Ollama** with a pulled instruct model. Optional `HF_TOKEN` if MiniLM download is rate-limited. |
| **Samples** | Quick demos + playbook PDFs + golden `playbook_config.json` in the repo. |
| **Accounts** | Demo users after `bootstrap_demo_users`. |

Full rationale: [`docs/13-HANDOFF.md`](docs/13-HANDOFF.md).

### Evaluator path — intended (real generative AI)

```bash
# From zip: unzip … && cd RedlineGuard
# Or: git clone https://github.com/New-Sheep/RedlineGuard.git && cd RedlineGuard

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env          # Windows; or: cp .env.example .env
```

Edit `.env` (required for the intended demo):

```env
FAKE_LLM=0
FAKE_EMBED=0
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=your_key_here
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
# Optional if MiniLM download fails: HF_TOKEN=...
```

**Ollama instead of NVIDIA:** set `LLM_PROVIDER=ollama`, install [Ollama](https://ollama.com), `ollama pull qwen2.5:7b-instruct` (or your `OLLAMA_MODEL`), leave cloud keys empty.

```bash
python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents
python manage.py check_llm --draft    # smoke the real LLM
python manage.py runserver
```

First `runserver` with `FAKE_EMBED=0` warms **MiniLM** (one-time download). Then open http://127.0.0.1:8000/ → sign in **`lawyer` / `lawyer-demo-2026`** → **Upload** → Quick demos or your own PDF/DOCX/TXT.

Admin: **`admin` / `admin-demo-2026`**.

### What the real AI path unlocks

With `FAKE_LLM=0`: playbook propose from PDF, suggested counters / rewrite co-pilot, L2 judge on flags, memory explain, decision brief, plain-English gloss, scoped ask. With `FAKE_EMBED=0`: proper semantic decision memory (not hash stubs).

### Fallback only (no API key / no Ollama)

If you cannot reach a model, set `FAKE_LLM=1` and `FAKE_EMBED=1`. The UI and playbook/security flows still run; **drafts are canned fixtures** — fine for smoke tests, **not** the AI Pioneer story.

---

## Approach (for reviewers)

| Idea | What it means here |
|------|--------------------|
| Playbook compiler | Flags cite company rules in `playbook_config.json` — not generic “AI vibes” |
| Setup co-pilot | PDF import **or** starter from past contracts proposes rules via LLM; lawyer **Activates** |
| Decision memory | Clause-excerpt Chroma + MiniLM; Memory page; provenance; Reject=Avoid |
| Override | “Override & accept as-is” appends to overrides — **never** rewrites the golden playbook |
| Security | Uploads untrusted; sanitize + injection halt; adjudicator; **25 MB** cap |
| Ingest | PDF / **DOCX** / TXT |
| Live progress | Background analyze; Processing page shows steps |
| Generative drafts | Real NVIDIA/Ollama/etc. when `FAKE_LLM=0` |
| UI | Django templates — no React dependency |

## Start here (read in order)

1. **[Handoff](docs/13-HANDOFF.md)** — delivery + AI setup  
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
| **Demo — hostile / injection** / Hostile sample | C — Security alert (on full GitHub tree) |

Playbook PDFs: `data/playbook_corpus/`. **Text-based PDFs only** for uploads; scanned image PDFs fail with a clear message — use a Quick demo first.

## LLM providers (detail)

| `LLM_PROVIDER` | Backend |
|----------------|---------|
| `nvidia` (recommended) | NVIDIA NIM / build.nvidia.com key |
| `auto` | First of NVIDIA → DeepSeek → Moonshot keys, else Ollama |
| `ollama` | Local Ollama (`OLLAMA_*`) |
| `deepseek` / `moonshot` / `http` | Other OpenAI-compatible HTTP |

Smoke: `python manage.py check_llm --draft`. If the live model is down or returns bad JSON, some draft paths may fall back to fixtures — fix keys/network rather than staying on Fake for the judged demo.

**L2 judge:** on when `FAKE_LLM=0`. Set `LLM_JUDGE=0` to skip.

**Security:** CSRF on mutating APIs; session roles; admin lab `/lab/`; audit append-only. Explainability: `/trust/`. Evals: `python -m evals.runners.run_all`.

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

- [ ] Journey **A:** demo clean sample → flags cite rules → Accept (with **live** LLM drafts)  
- [ ] Journey **B:** seed precedents *or* prior Accept → memory draft / Override  
- [ ] Journey **C:** hostile sample → Security alert  
- [ ] Journey **E1:** playbook PDF import → Activate (LLM propose)  
- [ ] Journey **E2:** `/playbook/starter/` with 3 samples → Activate  
- [ ] Confirm UI badge / drafts are **not** stuck on Fake fixtures  

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

Record the Loom on the **intended** path (`FAKE_LLM=0`, `FAKE_EMBED=0`) so reviewers see generative AI, not fixtures.

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
- Intended path: MiniLM locally + LLM over HTTPS to your chosen provider (or fully local Ollama)  

## Limitations

- Not legal advice  
- Playbook matching is layered (regex + semantic + optional LLM judge)  
- Overrides suppress whole rules (coarse)  
- Local SQLite + local Chroma  
- Not a production deploy — local demo only  
- Reviewers must supply their own LLM access (key or Ollama); keys are never shipped  

## Reference only (not MVP authority)

- `docs/03-SCRATCH-DRYRUN.md`, `docs/gemini_brainstorm.md`, `docs/CLAUDE_PORTSWIGGER.md`

**Conflict rule:** PRD + README + [`docs/13-HANDOFF.md`](docs/13-HANDOFF.md) win over vision docs.
