# Scratch lab — TDD dry-runs for RedlineGuard

Independent proof-of-concepts. Each step **prints** and **saves** artifacts so you can
watch a PDF transform: extract → security → triage → playbook → memory → **draft**.

## Setup

```bash
cd redlineguard
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r scratch/requirements-scratch.txt
```

- Corpus: `data/scratch_corpus/`
- Playbook (hard rules): `data/playbook_config.json`
- Vector memory (learning): `data/vector_memory/` (gitignored)
- Outputs: `scratch/out/<stem>/<timestamp>/` and `.../latest/`

**Embeddings**

| Mode | Flag / env | Backend |
|---|---|---|
| Offline / pytest (default) | `FAKE_EMBED=1` | HashEmbedder (no download) |
| Real semantic | `FAKE_EMBED=0` or `--real-embed` | MiniLM `all-MiniLM-L6-v2` via `sentence-transformers` |

**Important:** do not mix hash and MiniLM vectors in the same Chroma collection — reset
`data/vector_memory/` (or the collection) when switching embedders.

**Drafting:** Step 06 uses `FakeDraftEngine` (no network LLM). Precedents win over
playbook fallback text. A real multi-provider LLM can later implement the same
`DraftEngine` interface.

## Run one step at a time

From repo root (`redlineguard/`):

```bash
python -m scratch.poc01_extract.extract data/scratch_corpus/MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf
python -m scratch.poc02_security.security data/scratch_corpus/injection_hostile.txt
python -m scratch.poc03_triage.triage data/scratch_corpus/MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf
python -m scratch.poc04_playbook.playbook data/scratch_corpus/MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf
```

## Learning loop (retrieve → draft → decide → write-back)

```bash
# Full dry-run (hash embeddings by default)
python -m scratch.05_dry_run_cli data/scratch_corpus/MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf

# Real MiniLM embeddings
python -m scratch.05_dry_run_cli --real-embed data/scratch_corpus/cyber-security-contract-template.pdf

# Accept all non-empty drafts into Chroma (match embedder!)
python -m scratch.poc07_draft.decide_cli --real-embed --from-out scratch/out/.../latest --all-accept

# Or a single finding
python -m scratch.poc07_draft.decide_cli --from-out .../latest --rule-id governing_law_preferred --decision edit --final "..."
```

### Real MiniLM + cyber-doc Accept (recommended)

Resets collection `cyber_minilm`, dry-runs the new cyber PDFs with MiniLM, Accepts
drafts, then re-runs to assert `draft_source=memory_precedent`:

```bash
python scratch/run_real_minilm_cyber_learning.py
```

Offline demos (hash embedder):

```bash
python scratch/run_memory_learning_demo.py
python scratch/run_draft_learning_demo.py
```

## Full journey (live banners)

```bash
python -m scratch.05_dry_run_cli data/scratch_corpus/MasterPatentIPLicenseandDevelopmentAgreementVer2.0.pdf
python -m scratch.05_dry_run_cli --all-corpus
```

Open `scratch/out/<stem>/latest/journey.md` (Steps 05 + 06).

## Tests

```bash
set FAKE_EMBED=1
pytest scratch/ -q
```

## Package names

`poc01_extract` … `poc07_draft`. Artifact files use `01_` … `06_`.
