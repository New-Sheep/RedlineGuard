# Scratch dry-run lab

See [`scratch/README.md`](../scratch/README.md) for commands.

## Purpose

Before Django, prove each RedlineGuard seam against real PDFs with **visible**
step outputs (console + `scratch/out/`).

## Pipeline

1. Extract (+ quality gate)  
2. Security (sanitize / fence / injection halt)  
3. Triage (Friday card)  
4. Playbook (hard JSON rules — not auto-learning)  
5. **Memory** — retrieve Accept/Edit/Reject precedents from local Chroma  
6. **Draft** — `FakeDraftEngine` (no real LLM): memory precedent → else playbook fallback → else none  
7. **Decide** (CLI) — Accept / Edit / Reject writes back to Chroma  

## Learning vs playbook

| Store | Updates how? |
|---|---|
| `playbook_config.json` | Hand-edited governance only |
| `data/vector_memory/` (Chroma) | `decide_cli` / `record_cli` / `seed_from_findings` |

Malicious PDFs that **HALT** at security never draft and never write to memory.

## Draft sources

| `draft_source` | Meaning |
|---|---|
| `memory_precedent` | Nearest prior accept/edit `final_text` |
| `playbook_fallback` | Finding’s `suggested_counter_proposal` |
| `none` | Needs human; no inventing text |

## Corpus → expected Sarah moment

| File | Expect |
|---|---|
| Master Patent IP License | Findings + drafts; after accept, Step 06 shows `memory_precedent` |
| Yale start-up license sample | Non-negotiable / indemnity / foreign law flags |
| Founders agreement | Kind `founders_template` |
| Tippett tenancy (scan) | `quality=poor`; later steps skipped |
| `injection_hostile.txt` / malicious corpus | Security **HALT**; no memory pollution |

## Mapping to MVP

| Scratch POC | Future app module |
|---|---|
| `poc01_extract` | `apps/contracts` |
| `poc02_security` | `apps/security` |
| `poc03_triage` | Review summary card |
| `poc04_playbook` | `apps/review` |
| `poc06_memory` | `apps/learning` / decisions |
| `poc07_draft` | draft engine + Accept UI |
| `05_dry_run_cli` | Orchestration sketch |

```bash
python scratch/run_memory_learning_demo.py
python scratch/run_draft_learning_demo.py
```
