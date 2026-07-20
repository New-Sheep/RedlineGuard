# Handoff — how PortSwigger tries RedlineGuard

**Audience:** take-home reviewers and anyone packaging a zip / GitHub clone.  
**Authority:** this file + [`README.md`](../README.md). Vision docs that mention Docker or cloud deploy are **aspirational only**.

---

## Decision (what we ship)

| Question | Answer |
|----------|--------|
| Deploy to a public URL? | **No.** Brief is local try + Loom/video. No Railway/Vercel/OCI hosting for this exercise. |
| Windows `.exe` installer? | **No.** Wrong fit for a Django prototype; security engineers already have Python. |
| Docker Compose? | **Not shipped.** Optional later; do not claim `docker compose up` until a real compose file exists. |
| How do they get the code? | **Zip of the same tree** (submission) or **GitHub clone**. |
| Sample / Quick-demo docs? | **Yes — committed.** Reviewers must not hunt for external NDAs. |
| Cloud LLM keys required? | **No.** Default path is fully offline (`FAKE_LLM=1`). |

---

## What is in the repo for first-time use

| Asset | Path | Why |
|-------|------|-----|
| Quick demos (Upload buttons + dropdown) | `data/scratch_corpus/demo_*.txt`, `injection_hostile.txt` | Journeys A and C in one click |
| Golden playbook | `data/playbook_config.json` | Flags cite real company rules out of the box |
| Playbook import samples | `data/playbook_corpus/` | Journey E1 (Activate flow) |
| Hostile / injection samples | `data/malicious_corpus/` + hostile TXT | Journey C / security story |
| Precedent seed (optional) | `data/precedents/` + `seed_precedents` | Journey B without a prior Accept |
| Demo accounts | `bootstrap_demo_users` | `lawyer` / `admin` for session auth demos |
| Env template | `.env.example` | Copy to `.env` only if you change defaults |

Runtime-only (gitignored, recreated on first run): `db.sqlite3`, `media/`, Chroma under `data/vector_memory/`, `.env`.

---

## Evaluator path (target: under 10 minutes)

Requires **Python 3.11+** and Git (or an unzipped folder).

```bash
git clone https://github.com/New-Sheep/RedlineGuard.git
cd RedlineGuard

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env          # Windows; or: cp .env.example .env

# Fast offline first run (no MiniLM download, no cloud LLM):
# In .env set:  FAKE_LLM=1   and   FAKE_EMBED=1
# Or for this shell only:
set FAKE_LLM=1
set FAKE_EMBED=1

python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents   # optional — Journey B cold start
python manage.py runserver
```

1. Open http://127.0.0.1:8000/ → sign in **`lawyer` / `lawyer-demo-2026`**
2. Complete or skip onboarding
3. **Upload** → click **Sample with issues** (or Short NDA / Hostile sample)
4. Walk Review → Rewrite → Accept; try Hostile for the security halt

Admin lab (resets): `admin` / `admin-demo-2026` at `/lab/`.

---

## Why not Docker or an installer?

- **PortSwigger reviewers** are engineers: clone + venv is normal; they will judge the *product and security story*, not packaging polish.
- Docker would need a maintained image, migrate-on-start, and Fake LLM defaults — nice later, not required for MVP Must N4 (“local zip-friendly run”).
- An `.exe` would freeze a large Python tree, fight antivirus, and hide how the app actually runs — poor signal for this brief.

---

## What we do *not* put in git

- Secrets, `.env` with API keys, OCI wallets  
- Local SQLite / Chroma / uploaded `media/`  
- A privately mutated playbook that breaks the demo samples  

Before push or zip: confirm Quick demos still flag against `data/playbook_config.json`.

---

## Loom / smoke (same as README)

- **A:** Demo clean → flags cite rules → Accept → Memory  
- **B:** Re-analyze or `seed_precedents` → provenance / Override  
- **C:** Hostile sample → Security alert  
- **E:** Playbook import or starter → Activate  

Offline check: `FAKE_LLM=1` + `FAKE_EMBED=1` still completes Analyze.

---

## Doc map for outsiders

| Read first | Purpose |
|------------|---------|
| [`README.md`](../README.md) | Run + demo journeys |
| This file | Delivery decisions |
| [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) | Product in plain English |
| [`01-PRD-MVP.md`](01-PRD-MVP.md) | Scope (Must / Won’t) |
| [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) | Flows and statuses |
| [`CLAUDE_PORTSWIGGER.md`](CLAUDE_PORTSWIGGER.md) | Vision only — **not** how to run |

**Conflict rule:** PRD + README + this handoff beat vision docs.
