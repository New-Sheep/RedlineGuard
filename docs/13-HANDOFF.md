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
| **Intended AI path** | **Real LLM + MiniLM.** `FAKE_LLM=0`, `FAKE_EMBED=0`. Reviewer brings **NVIDIA API key** *or* **Ollama**. |
| Fake fixtures? | **Fallback only** when no model is available — not the judged demo story. |

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
| Env template | `.env.example` | Copy to `.env`, then **add your LLM key** |

Runtime-only (gitignored, recreated on first run): `db.sqlite3`, `media/`, Chroma under `data/vector_memory/`, `.env`, MiniLM cache.

---

## Evaluator path — intended (real generative AI)

Requires **Python 3.11+**, Git (or unzip), and **one** of:

- **NVIDIA API key** from [build.nvidia.com](https://build.nvidia.com) (recommended), or  
- **Ollama** installed locally with an instruct model pulled (e.g. `qwen2.5:7b-instruct`)

```bash
git clone https://github.com/New-Sheep/RedlineGuard.git
cd RedlineGuard

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env          # Windows; or: cp .env.example .env
```

Edit `.env`:

```env
FAKE_LLM=0
FAKE_EMBED=0
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=paste_your_key
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
```

Optional: `HF_TOKEN=…` if the MiniLM download from Hugging Face is rate-limited.

```bash
python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents
python manage.py check_llm --draft
python manage.py runserver
```

1. Open http://127.0.0.1:8000/ → sign in **`lawyer` / `lawyer-demo-2026`**
2. Complete or skip onboarding
3. **Upload** → **Sample with issues** (or Short NDA / Hostile sample)
4. Walk Review → Rewrite → Accept; confirm drafts look like live model output, not stub text
5. Try Hostile for the security halt; try playbook PDF import for LLM propose

Admin lab (resets): `admin` / `admin-demo-2026` at `/lab/`.

### Fallback (no model access)

Set `FAKE_LLM=1` and `FAKE_EMBED=1`. UI/security/playbook still work; **drafts are fixtures**. Use only if you cannot reach NVIDIA or Ollama.

---

## Why not Docker or an installer?

- **PortSwigger reviewers** are engineers: clone + venv + their own LLM access is normal.
- Docker would need a maintained image and migrate-on-start — nice later, not required for this take-home.
- An `.exe` would freeze a large Python tree and hide how the app runs — poor signal for this brief.

---

## What we do *not* put in git

- Secrets, `.env` with API keys, OCI wallets  
- Local SQLite / Chroma / uploaded `media/`  
- A privately mutated playbook that breaks the demo samples  

Before push or zip: confirm Quick demos still flag against `data/playbook_config.json`.

---

## Loom / smoke (same as README)

Record on the **intended** path (`FAKE_LLM=0`, `FAKE_EMBED=0`):

- **A:** Demo clean → flags cite rules → live draft → Accept → Memory  
- **B:** Re-analyze or `seed_precedents` → provenance / Override  
- **C:** Hostile sample → Security alert  
- **E:** Playbook import or starter → Activate  

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
