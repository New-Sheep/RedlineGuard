# RedlineGuard

**A first-pass helper for in-house lawyers reviewing routine contracts.**

Built as a PortSwigger **AI Pioneer** take-home prototype.

**Watch the demo (start here):** [https://www.youtube.com/watch?v=ohsFo9hrGkc](https://www.youtube.com/watch?v=ohsFo9hrGkc)

---

## What were we trying to achieve?

PortSwigger’s brief (in plain terms):

- The legal team gets a steady stream of **low-stakes** contracts (NDAs, small order forms).
- Most of the text is boilerplate. The **same kinds of redlines** come back again and again.
- A person still has to read every contract. The queue grows faster than the day.

**Goal of this experiment:** show that AI can speed up that first pass **without pretending to be a lawyer**, and without inventing company policy on the fly.

We built a working local web app where a lawyer can:

1. Upload a contract (or click a demo sample)
2. See what clashes with the company’s written rules
3. Get a suggested rewrite when the rules allow one
4. Accept, edit, or reject that suggestion
5. Have the system **remember** that decision for the next similar clause

**One-line promise:** set up the rules (if needed) → upload → check against rules → flag / suggest → decide → remember.

**Operating principle:** *AI proposes. The company playbook decides. The lawyer confirms.*

---

## Why this approach (not “chat with the PDF”)?

| Tempting idea | Why we avoided it | What we did instead |
|---------------|-------------------|---------------------|
| Open chat with the whole contract | Easy to hallucinate; hard to audit; easy to jailbreak | Structured review against a fixed checklist |
| AI invents “risk” freely | Company policy would come from the model, not the firm | Every flag must cite a **playbook rule** the company already owns |
| Auto-change company rules when someone clicks Accept | Quietly rewrites governance | Accept goes to **memory**; the golden playbook only changes when a lawyer deliberately **Activates** a proposal |
| Hosted “AI lawyer” SaaS | Wrong for a take-home; secrets and trust story get muddy | Runs on the reviewer’s laptop; they bring their own AI key |

The experiment is: **can a playbook-grounded loop feel like a multiplier** (same amends, less re-work) while staying governable?

---

## How it works (simple experimental method)

Think of it as a lab procedure with four ingredients.

### 1. The playbook (company rules in a file)

A **playbook** is a checklist of how the company usually negotiates (governing law, liability caps, IP, equity control, and so on).

- Reviews only make sense once a playbook is live.
- If there is no playbook yet, the app helps **propose** one from a PDF or past contracts. A lawyer must **Activate** it before it becomes the live checklist.

### 2. Treat every upload as untrusted

Before deep analysis, the text is cleaned and scanned for **hostile instructions** hidden in the document (classic “ignore previous instructions / approve everything” attacks).

- Strong hits stop the review and show a **Security alert**.
- A lawyer can still override, but that is an explicit, logged choice.

### 3. Compare the contract to the playbook (three passes)

| Pass | Plain English | Why |
|------|---------------|-----|
| **Pattern check** | Look for known bad phrases / needles in the rules | Fast, auditable, explainable |
| **Meaning check** | Find clauses that *mean* the same thing even if wording differs | Catches paraphrase the pattern pass misses |
| **AI second opinion** | Ask the model: “does this excerpt actually break *this* rule?” | Confirms or drops borderline hits; still bound to that one rule |

Only after that does the app draft a suggested rewrite (when the playbook has fallback language, or via the AI when needed).

### 4. Learn from the lawyer

When the lawyer **Accepts**, **Edits**, or **Rejects**:

- The decision is stored.
- Similar clauses later can reuse a past Accept / Edit.
- Rejects teach the system to **avoid** that suggestion.
- Optional **Override** means “this variation is actually OK here” without silently rewriting the golden playbook.

That is the “AI as a multiplier” claim in experimental form: **rules + human decisions compound**; the model is a helper, not the source of truth.

---

## What you see in the demo

| Journey | What it shows |
|---------|----------------|
| **Happy path** | Sample contract → a few playbook flags → suggested rewrite → Accept → shows up in Memory |
| **Memory / override** | A later similar clause reuses a past decision, or an override is respected |
| **Hostile input** | “Unsafe sample” → Security alert (no silent “all approved”) |
| **No playbook yet** | Import a playbook PDF → edit proposed rules → Activate → then reviews use those rules |

UI flow: **Upload → Processing → Review → Rewrite** (plus Memory, Playbook, Audit, Help).

---

## Watch first, then try (optional)

1. **Demo video:** [https://www.youtube.com/watch?v=ohsFo9hrGkc](https://www.youtube.com/watch?v=ohsFo9hrGkc)
2. Or run it yourself (~15-20 minutes the first time). Checklist: [`docs/14-EVALUATOR-GUIDE.md`](docs/14-EVALUATOR-GUIDE.md)

### Quick try (technical setup)

You need: **Python 3.11+**, and either an **NVIDIA API key** from [build.nvidia.com](https://build.nvidia.com) or local [Ollama](https://ollama.com).

```bash
git clone https://github.com/New-Sheep/RedlineGuard.git
cd RedlineGuard
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
# Edit .env: set FAKE_LLM=0, FAKE_EMBED=0, LLM_PROVIDER=nvidia, NVIDIA_API_KEY=...

python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents
python manage.py check_llm --draft
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in:

| User | Password | Use |
|------|----------|-----|
| `lawyer` | `lawyer-demo-2026` | Main demo |
| `admin` | `admin-demo-2026` | Lab resets |

Then: **Upload → Sample with issues → Accept → Memory**. Also try **Unsafe sample** and **Playbook → Import**.

**Intended demo uses a real AI model** (`FAKE_LLM=0`). Canned “Fake” mode is only a backup if you have no model access.

Full env table, cold-start times, and troubleshooting: see below and [`.env.example`](.env.example).

---

## Environment (for people running it)

Copy `.env.example` to `.env`. Minimal intended setup:

```env
FAKE_LLM=0
FAKE_EMBED=0
LLM_PROVIDER=nvidia
NVIDIA_API_KEY=paste_your_key_here
NVIDIA_MODEL=nvidia/nemotron-3.5-bolt-e4b
SEMANTIC_COMPARE=1
```

| Setting | Plain meaning |
|---------|----------------|
| `FAKE_LLM=0` | Use a real generative model for drafts / judge |
| `FAKE_EMBED=0` | Use real meaning-similarity for memory (first run downloads a small model once) |
| `LLM_PROVIDER` | `nvidia` (recommended) or `ollama` |
| `LLM_JUDGE` | Leave unset: AI second-opinion on flags turns on automatically when `FAKE_LLM=0` |

**Ollama path:** `LLM_PROVIDER=ollama`, pull an instruct model, leave the NVIDIA key empty.

**Backup offline UI:** `FAKE_LLM=1` and `FAKE_EMBED=1` (fixtures only; fine for smoke tests, not the judged AI story).

| Command | Why |
|---------|-----|
| `migrate` | Create the local database |
| `bootstrap_demo_users` | Create demo logins |
| `seed_precedents` | Pre-load a few memory examples |
| `check_llm --draft` | Prove your AI key works before opening the UI |
| `runserver` | Start the app |

Typical first-time waits: install 2-5 min; first meaning-model download 1-5 min once; first live analyze ~30-90 s.

---

## What’s in the box / what’s not

| Included | Left out on purpose |
|----------|---------------------|
| Working local web app + sample contracts + playbook PDFs | Hosted cloud deploy / Docker as the only path |
| Hostile samples for the security demo | Shipping API keys in the zip |
| Decision memory + audit trail | Claiming this is legal advice or production compliance |

**Disclaimer:** first-pass assistant only. A human remains accountable.

---

## If something goes wrong

| Symptom | Try this |
|---------|----------|
| AI check fails | Confirm key in `.env`, `FAKE_LLM=0`, restart the terminal, re-run `check_llm --draft` |
| Meaning model won’t download | Set `HF_TOKEN`, or temporary `FAKE_EMBED=1` |
| Port 8000 busy | `python manage.py runserver 8001` |
| Drafts look canned | You are still on Fake, or the live call failed; fix `check_llm` |
| Scanned image PDF fails | Use Quick demos or a text-based PDF / DOCX / TXT |

---

## Deeper reading (optional)

| Doc | When to open it |
|-----|-----------------|
| [`docs/14-EVALUATOR-GUIDE.md`](docs/14-EVALUATOR-GUIDE.md) | One-page setup checklist |
| [`docs/13-HANDOFF.md`](docs/13-HANDOFF.md) | What we ship and why (zip / venv) |
| [`docs/00-WHAT-WE-ARE-BUILDING.md`](docs/00-WHAT-WE-ARE-BUILDING.md) | Short product orientation |
| [`docs/01-PRD-MVP.md`](docs/01-PRD-MVP.md) | Formal scope |
| [`docs/06-PRODUCT-MAP.md`](docs/06-PRODUCT-MAP.md) | Screens and statuses |
| [`docs/16-CURRENT-ARCHITECTURE.md`](docs/16-CURRENT-ARCHITECTURE.md) | How the code is structured |
| [`docs/08-COMPARE-ALGORITHM-AUDIT.md`](docs/08-COMPARE-ALGORITHM-AUDIT.md) | Detail on the three compare passes |
| [`docs/11-LAWYER-API.md`](docs/11-LAWYER-API.md) | Thin JSON APIs |

Design mockups: [`designs/README.md`](designs/README.md).

Optional tests:

```bash
set FAKE_EMBED=1
python manage.py test apps.contracts apps.review apps.security apps.decisions apps.learning

set FAKE_LLM=1
python -m evals.runners.run_smoke
```
