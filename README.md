# RedlineGuard

Take-home prototype for PortSwigger’s AI Pioneer brief: **playbook-grounded** first-pass contract review for in-house legal — with lite security and decision memory.

**One-line promise:** Set up playbook (if needed) → upload → check playbook → flag/counter → decide → remember.

**Principle:** AI proposes. The playbook decides. The lawyer confirms.

## Approach (for reviewers)

| Idea | What it means here |
|------|--------------------|
| Playbook compiler | Flags cite company rules in `playbook_config.json` — not generic “AI vibes” |
| Setup co-pilot | PDF import proposes rules; Sarah **Activates** (human gate). Empty playbook = onboarding, not invented flags |
| Decision memory (B1 / Sprint 5) | Clause-excerpt Chroma (`django_decisions_v2`); Memory page; provenance; Reject=Avoid; distance gate |
| Override (B2) | “Override & accept as-is” appends to `playbook_overrides.json` — **never** rewrites the golden playbook |
| Security | Uploads are untrusted; sanitize + injection halt; playbook PDFs use a stricter-but-chrome-tolerant gate |
| Live progress | Analyze runs in the background; Processing page shows steps (reading → security → playbook → draft) |
| LLM drafts | Needs-human flags get suggested counters via `FAKE_LLM` (default Fake) or optional real API |
| UI (PactPilot SSR port) | Same risk colors / cockpit patterns as PactPilot, in Django templates — no React dependency |

## Start here (read in order)

1. **[What are we building?](docs/00-WHAT-WE-ARE-BUILDING.md)** — plain English  
2. **[Product map](docs/06-PRODUCT-MAP.md)** — **flows, statuses, decisions, DB (read this)**  
3. **[MVP PRD](docs/01-PRD-MVP.md)** — Must / Should / Could / Won’t  
4. **[MVP Implementation](docs/02-MVP-IMPLEMENTATION.md)** — stack, modules, build order  
5. **[Scratch foundation](docs/04-SCRATCH-FOUNDATION.md)** — CLI lab that seeded the Django services  
6. **[Django backend plan](docs/05-DJANGO-BACKEND-PLAN.md)** — modular monolith  
7. **[Stitch designs](designs/README.md)** — four screens (ignore Team/Archive chrome)  

## Run the Django app

```bash
cd redlineguard
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Decision memory uses **MiniLM** by default (`FAKE_EMBED=0`). The model **warms at server start** so the first Analyze click is not the cold spike. For offline/hash embeddings: `set FAKE_EMBED=1`.

LLM drafts for Needs-human flags default to **Fake** (`FAKE_LLM=1`). Optional real OpenAI-compatible API: copy [`.env.example`](.env.example), set `FAKE_LLM=0` and `LLM_API_KEY=...`.

Open http://127.0.0.1:8000/

### Demo samples (use these first)

| Sample in dropdown | Journey |
|--------------------|---------|
| **Demo — clean contract (2–4+ playbook flags)** | A — Review → rewrite → Accept |
| **Demo — short form (2 flags)** | A — quicker path |
| **Demo — hostile / injection** | C — Security alert |

### Contracts

- Analyze → security → playbook compare → draft → **Review** (document + flags)
- **Rewrite:** Accept / Edit / Reject / **Override & accept as-is**
- **History** at `/history/` · **Memory** at `/memory/` (precedents, Unlearn, overrides)

### Playbook (no JSON for lawyers)

1. `/playbook/` — active rules  
2. **Import playbook** → Sample Playbook1.pdf → edit → **Activate** (`.bak` of previous golden file)  
3. Poisoned Sample Playbook2 → **halted**, cannot Activate  

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
2. **B:** Re-analyze similar text → Rewrite shows **provenance** (reused from filename) **or** Override one rule → that rule no longer flags  
3. **C:** Upload `Demo — hostile / injection` → Security alert  
4. **(Optional):** Reject → Avoid on Memory; Unlearn a precedent; `/api/memory/` in Network tab 

## Security posture (honest)

- Heuristic injection detection + sanitize; halt on high-confidence hits  
- Contract path treats Gemini chat-export chrome as hostile; playbook import does not (real playbooks often come from Gemini)  
- Prototype only — not production privacy/compliance; no secrets in git  
- Offline path: `FAKE_EMBED=1` (hash embeddings); demo default is MiniLM (`FAKE_EMBED=0`). Playbook compare is heuristic (no cloud LLM required for flags)

## Limitations

- Not legal advice  
- Heuristic playbook matching (not full LLM legal reasoning yet)  
- Overrides suppress whole rules (coarse)  
- Local SQLite + local Chroma  

## Reference only (not MVP authority)

- `docs/03-SCRATCH-DRYRUN.md`, `docs/gemini_brainstorm.md`, `docs/CLAUDE_PORTSWIGGER.md`

**Conflict rule:** PRD + Implementation win over vision docs.
