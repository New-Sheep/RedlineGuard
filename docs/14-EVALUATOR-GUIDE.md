# Evaluator guide (one page)

Print or keep open while you set up. Full detail: [`../README.md`](../README.md).

## Prerequisites

- [ ] Python 3.11+
- [ ] NVIDIA API key ([build.nvidia.com](https://build.nvidia.com)) **or** Ollama + pulled instruct model
- [ ] Optional: Hugging Face token if MiniLM download fails

## Setup

```bash
cd RedlineGuard          # after unzip or git clone
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt          # ~2–5 min
copy .env.example .env                   # or: cp .env.example .env
```

Edit `.env`:

- [ ] `FAKE_LLM=0`
- [ ] `FAKE_EMBED=0`
- [ ] `LLM_PROVIDER=nvidia` (or `ollama`)
- [ ] `NVIDIA_API_KEY=...` filled in (unless Ollama)

```bash
python manage.py migrate
python manage.py bootstrap_demo_users
python manage.py seed_precedents
python manage.py check_llm --draft       # must succeed for live AI demo
python manage.py runserver
```

## Login

| User | Password |
|------|----------|
| `lawyer` | `lawyer-demo-2026` |
| `admin` | `admin-demo-2026` |

URL: http://127.0.0.1:8000/

## Cold start (expect once)

| Step | Time |
|------|------|
| pip install | ~2–5 min |
| First MiniLM | ~1–5 min |
| check_llm | ~10–60 s |
| First analyze | ~30–90 s |

## Demo journeys

- [ ] **A:** Upload → Sample with issues → Review → Accept → Memory  
- [ ] **B:** Memory / Override (after seed or prior Accept)  
- [ ] **C:** Unsafe sample → Security halt  
- [ ] **E:** `/playbook/` → import PDF → Activate  

## You are done when

Live LLM drafts appear (not Fake stubs), flags cite playbook rules, and Accept lands on Memory.

## If stuck

| Issue | Fix |
|-------|-----|
| LLM check fails | Fix key / provider; re-run `check_llm --draft` |
| No MiniLM | Set `HF_TOKEN` or temporary `FAKE_EMBED=1` |
| Need offline UI only | `FAKE_LLM=1` + `FAKE_EMBED=1` (not the judged path) |

Architecture / APIs: README sections + [`11-LAWYER-API.md`](11-LAWYER-API.md) · [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) · designs: [`../designs/README.md`](../designs/README.md)
