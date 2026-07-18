# What are we actually building?

**Read this before vision docs (`CLAUDE_PORTSWIGGER.md`, raw Gemini notes).**  
If those conflict with this file or the [MVP PRD](01-PRD-MVP.md), **the MVP wins**.

---

## In one sentence

**RedlineGuard** helps an in-house lawyer upload a routine contract, check it against the company’s written rules (a **playbook**), see what doesn’t match, get a suggested rewrite when the playbook allows one, and Accept / Edit / Reject — so the next similar contract is easier.

---

## Who is it for?

**Sarah** — lawyer inside PortSwigger (not a law firm). Queue of mutual NDAs, small order forms, mostly boilerplate. Same redlines keep coming back. End of month/quarter gets overwhelming.

She needs a **first-pass co-pilot**, not a chatbot and not “AI lawyer.”

We are **not** building for a small-business founder (that was PactPilot).

---

## What “AI as a multiplier” means here

Passive AI: “Here’s a summary / some risks.”  

**Multiplier (what we want):**

1. Rules live in a **playbook file** (governance can change without rewriting the app)  
2. The model only judges **against that playbook** (closed-book — doesn’t invent random legal compromises)  
3. Sarah’s Accept / Edit / Reject (and optional “override, this is OK”) **feeds the next review**  

That’s how we address “amends we’ve seen before.”

**Setup when there’s no playbook yet:** we don’t invent company policy on the fly. We treat it as onboarding — clear empty state, upload a playbook PDF or a few past contracts, AI proposes rules, Sarah reviews and **activates**. Only then do reviews produce real flags. Memory still helps after findings exist; it doesn’t invent the first checklist.

**Principle:** AI proposes. The playbook decides. The lawyer confirms.

---

## The MVP loop

```
(If no playbook yet: empty state → propose rules from PDF or past contracts → Sarah activates)
Upload PDF (or sample)
    → Security: treat text as untrusted (clean + fence before AI)
    → Compare to playbook_config.json
    → Show flagged bits (highlighted) + which rule they broke
    → Suggest rewrite IF the playbook has fallback text
       else mark “Needs human”
    → Accept / Edit / Reject
    → Remember (decision history and/or playbook override)
```

**Also must demo:** a nasty sample that tries to trick the AI (“ignore instructions…”) — we block or clearly neutralise it. Same idea for a **poisoned playbook PDF** — halt; don’t let it become the company rules.

---

## Screens (still four + a couple of small extras)

Visuals: [`designs/`](../designs/) — Upload → Processing → Review → Rewrite.

| Screen | Job |
|---|---|
| Upload | Get a PDF / sample in; “Not legal advice” |
| Processing | Reading → security check → playbook compare |
| Review | Contract + flags (each flag cites a playbook rule) |
| Rewrite | Original vs suggested; Accept / Edit / Reject |
| Security alert | When injection-style input is caught |
| History (simple) | Past decisions |
| Playbook view | Active rules we’re checking |
| Playbook setup | Empty state → import PDF / past contracts → edit proposal → Activate |

Ignore Stitch’s Dashboard / Team / Archive chrome.

---

## Journeys you must be able to show

**A — Happy path:** sample contract → 2–4 playbook flags → rewrite → Accept.  

**B — Multiplier:** either (1) second contract reuses a prior Accept in the draft, and/or (2) “Override & accept” writes an exception the next run respects.  

**C — Security:** injection sample does **not** get a silent “all approved.”  

**E — No playbook yet:** empty state explains we can’t flag against *their* standards; upload playbook or past contracts → propose → review → Activate; then Journey A works. Poisoned playbook cannot Activate.

---

## What we are *not* building in MVP

| Skip | Why |
|---|---|
| Streamlit rewrite / new stack for fun | We already have a UI plan |
| Chat with the doc | Wrong product |
| Fancy multi-step AI agents | After MVP |
| Full enterprise security (hash chains, SSO, pen-test) | Demo lite + honest README |
| Auto-changing the company playbook every time Sarah clicks Accept | Learning goes to memory / overrides; golden playbook only changes when she deliberately Activates a reviewed proposal |
| Silent “AI risk flags” with no playbook | Trust requires citing company rules |
| Hosted Railway/Vercel unless they ask | Zip + local is enough |
| Fake “GDPR certified” badges | Don’t lie |

Details: [01-PRD-MVP.md](01-PRD-MVP.md). How the running app fits together: [06-PRODUCT-MAP.md](06-PRODUCT-MAP.md). How to build: [02-MVP-IMPLEMENTATION.md](02-MVP-IMPLEMENTATION.md).

---

## Success checklist

- [ ] Journey A works (sample + upload)  
- [ ] Flags cite playbook rules; “Needs human” when no fallback  
- [ ] Accept / Edit / Reject + history  
- [ ] Journey B demable  
- [ ] Journey C demable  
- [ ] Empty playbook = onboarding (not crash / not invented flags)  
- [ ] Propose → Activate human gate (PDF path at minimum)  
- [ ] Works with fake/offline AI mode  
- [ ] README: approach, data, security, limits, not legal advice  
- [ ] Short Loom  

---

## Plain-English jargon

| Word | Means |
|---|---|
| **Playbook** | The company’s written “how we usually negotiate” rules |
| **Activate** | Sarah confirms a proposed playbook — only then it becomes the live checklist |
| **Closed-book** | AI may only use the playbook + this contract — not invent policy |
| **Setup co-pilot** | AI helps draft a starter playbook; Sarah still owns governance |
| **Fence** | Wrap contract text in tags so the model treats it as data, not orders |
| **Prompt injection** | Hidden instructions inside a PDF to trick the AI |
| **Override** | Sarah says “this variation is actually OK” → stored for next time |

---

## Bottom line

**Set up the playbook (if needed) → upload → check playbook → flag/counter → decide → remember — with a basic shield against hostile PDFs.**

That’s the take-home. Vision docs are the sequel, not the homework.
