# Handoff — how PortSwigger tries RedlineGuard

**Audience:** take-home reviewers and anyone packaging a zip / GitHub clone.  
**Authority:** root [`README.md`](../README.md) for **how to run**. This file for **what we ship and why**.  
**One-pager checklist:** [`14-EVALUATOR-GUIDE.md`](14-EVALUATOR-GUIDE.md).

Vision docs that mention Docker or cloud deploy are **aspirational only**.

---

## Decision (what we ship)

| Question | Answer |
|----------|--------|
| Deploy to a public URL? | **No.** Local try + Loom/video. |
| Windows `.exe` / Docker? | **No.** Python venv is the supported path. |
| How do they get the code? | **Zip** (same tree) or **GitHub clone**. |
| Sample docs? | **Yes**, committed under `data/`. |
| **Intended AI path** | **Real LLM + MiniLM:** `FAKE_LLM=0`, `FAKE_EMBED=0`. Reviewer brings **NVIDIA API key** *or* **Ollama**. |
| Fake fixtures? | **Fallback only** when no model is available. |
| Secrets in zip/git? | **Never.** Copy `.env.example` → `.env` and fill keys locally. |

---

## Login (after `bootstrap_demo_users`)

| Username | Password | Role |
|----------|----------|------|
| `lawyer` | `lawyer-demo-2026` | Primary demo |
| `admin` | `admin-demo-2026` | Lab at `/lab/` |

Demo-only. Session auth on by default (`REQUIRE_AUTH=1`).

---

## Expected cold start

| Step | Typical |
|------|---------|
| `pip install -r requirements.txt` | ~2–5 min |
| First MiniLM download (`FAKE_EMBED=0`) | ~1–5 min once |
| `check_llm --draft` | ~10–60 s |
| First live analyze | ~30–90 s |

Full command meanings: [`README.md`](../README.md).

---

## What is in the repo for first-time use

| Asset | Path | Why |
|-------|------|-----|
| Quick demos | `data/scratch_corpus/demo_*.txt`, `injection_hostile.txt` | Journeys A and C |
| Golden playbook | `data/playbook_config.json` | Flags cite real rules |
| Playbook import samples | `data/playbook_corpus/` | Journey E1 |
| Hostile / injection samples | `data/malicious_corpus/` + hostile TXT | Journey C |
| Precedent seed | `data/precedents/` + `seed_precedents` | Journey B cold start |
| Demo accounts | `bootstrap_demo_users` | `lawyer` / `admin` |
| Env template | `.env.example` | Copy to `.env`, add LLM key |

Runtime-only (gitignored): `db.sqlite3`, `media/`, Chroma under `data/vector_memory/`, `.env`, MiniLM cache.

---

## Evaluator path (summary)

Prefer the numbered steps in [`README.md`](../README.md). Short form:

```bash
# unzip or: git clone https://github.com/New-Sheep/RedlineGuard.git
cd RedlineGuard
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env: FAKE_LLM=0 FAKE_EMBED=0 LLM_PROVIDER=nvidia NVIDIA_API_KEY=...
python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents
python manage.py check_llm --draft
python manage.py runserver
```

Then http://127.0.0.1:8000/ → `lawyer` / `lawyer-demo-2026` → Upload Quick demos.

**Fallback:** `FAKE_LLM=1` and `FAKE_EMBED=1` if no model access (fixtures only).

---

## Why not Docker or an installer?

PortSwigger reviewers are engineers: clone + venv + their own LLM access is normal. Docker and `.exe` would hide how the prototype runs and are out of scope for this take-home.

---

## What we do *not* put in git

- Secrets, `.env` with API keys  
- Local SQLite / Chroma / uploaded `media/`  
- A privately mutated playbook that breaks demo samples  

---

## Loom / smoke

Record on the **intended** path (`FAKE_LLM=0`, `FAKE_EMBED=0`):

- **A:** Demo clean → flags → live draft → Accept → Memory  
- **B:** seed precedents / prior Accept → provenance / Override  
- **C:** Hostile sample → Security alert  
- **E:** Playbook import or starter → Activate  

---

## Doc map

| Read first | Purpose |
|------------|---------|
| [`README.md`](../README.md) | Run + env + auth + architecture |
| [`14-EVALUATOR-GUIDE.md`](14-EVALUATOR-GUIDE.md) | One-page checklist |
| This file | Delivery decisions |
| [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) | Product plain English |
| [`01-PRD-MVP.md`](01-PRD-MVP.md) | Scope |
| [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) | Flows |
| [`11-LAWYER-API.md`](11-LAWYER-API.md) | JSON APIs |
| [`CLAUDE_PORTSWIGGER.md`](CLAUDE_PORTSWIGGER.md) | Vision only |

**Conflict rule:** PRD + README + this handoff beat vision docs.
