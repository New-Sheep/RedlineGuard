# Handoff (delivery decisions)

**Purpose:** What we ship to PortSwigger and why. **How to run:** [`../README.md`](../README.md). **One-page checklist:** [`14-EVALUATOR-GUIDE.md`](14-EVALUATOR-GUIDE.md).

---

## Delivery choices

| Question | Answer |
|----------|--------|
| How reviewers get the code | Zip (same tree) or GitHub clone |
| How they run it | Python 3.11+ venv (`pip install -r requirements.txt`) |
| Intended AI path | `FAKE_LLM=0`, `FAKE_EMBED=0` with NVIDIA API key or Ollama |
| Fake fixtures | Offline fallback when no model is available |
| Samples | Committed under `data/` |
| Secrets | Copy `.env.example` → `.env`; keys stay local |

Supported try path is clone + venv + reviewer LLM access (Loom/video for the demo).

---

## Login (after `bootstrap_demo_users`)

| Username | Password | Role |
|----------|----------|------|
| `lawyer` | `lawyer-demo-2026` | Primary demo |
| `admin` | `admin-demo-2026` | Lab at `/lab/` |

Session auth on by default (`REQUIRE_AUTH=1`).

---

## Cold start (typical)

| Step | Time |
|------|------|
| `pip install -r requirements.txt` | ~2-5 min |
| First MiniLM download (`FAKE_EMBED=0`) | ~1-5 min once |
| `check_llm --draft` | ~10-60 s |
| First live analyze | ~30-90 s |

Commands: [`../README.md`](../README.md).

---

## First-time assets

| Asset | Path |
|-------|------|
| Quick demos | `data/scratch_corpus/demo_*.txt`, `injection_hostile.txt` |
| Golden playbook | `data/playbook_config.json` |
| Playbook import samples | `data/playbook_corpus/` |
| Hostile PDFs | `data/malicious_corpus/` |
| Precedent seed | `data/precedents/` + `seed_precedents` |
| Env template | `.env.example` |

Runtime-only (gitignored): `db.sqlite3`, `media/`, Chroma under `data/vector_memory/`, `.env`, MiniLM cache.

---

## Loom / smoke (intended path)

- **A:** Sample with issues → flags → live draft → Accept → Memory
- **B:** Seed precedents / prior Accept → provenance / Override
- **C:** Hostile sample → Security alert
- **E:** Playbook import or starter → Activate

---

## Doc map

| Doc | Purpose |
|-----|---------|
| [`../README.md`](../README.md) | Run, env, architecture summary |
| [`14-EVALUATOR-GUIDE.md`](14-EVALUATOR-GUIDE.md) | Printable checklist |
| This file | Delivery decisions + asset inventory |
| [`00-WHAT-WE-ARE-BUILDING.md`](00-WHAT-WE-ARE-BUILDING.md) | Product plain English |
| [`01-PRD-MVP.md`](01-PRD-MVP.md) | Scope |
| [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) | Flows and statuses |
| [`16-CURRENT-ARCHITECTURE.md`](16-CURRENT-ARCHITECTURE.md) | As-built architecture |
| [`08-COMPARE-ALGORITHM-AUDIT.md`](08-COMPARE-ALGORITHM-AUDIT.md) | Compare L0/L1/L2 |
| [`11-LAWYER-API.md`](11-LAWYER-API.md) | Thin JSON APIs |
| [`15-LANGGRAPH-MULTI-AGENT-ARCHITECTURE.md`](15-LANGGRAPH-MULTI-AGENT-ARCHITECTURE.md) | Planned multi-agent vision |

**Authority:** PRD + README + this handoff for the take-home; vision docs are sequel only.
