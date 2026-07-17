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

---

## The MVP loop

```
Upload PDF (or sample)
    → Security: treat text as untrusted (clean + fence before AI)
    → Compare to playbook_config.json
    → Show flagged bits (highlighted) + which rule they broke
    → Suggest rewrite IF the playbook has fallback text
       else mark “Needs human”
    → Accept / Edit / Reject
    → Remember (decision history and/or playbook override)
```

**Also must demo:** a nasty sample that tries to trick the AI (“ignore instructions…”) — we block or clearly neutralise it.

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
| Playbook view (nice) | Read-only list of rules we’re checking |

Ignore Stitch’s Dashboard / Team / Archive chrome.

---

## Journeys you must be able to show

**A — Happy path:** sample contract → 2–4 playbook flags → rewrite → Accept.  

**B — Multiplier:** either (1) second contract reuses a prior Accept in the draft, and/or (2) “Override & accept” writes an exception the next run respects.  

**C — Security:** injection sample does **not** get a silent “all approved.”  

---

## What we are *not* building in MVP

| Skip | Why |
|---|---|
| Streamlit rewrite / new stack for fun | We already have a UI plan |
| Chat with the doc | Wrong product |
| Fancy multi-step AI agents | After MVP |
| Full enterprise security (hash chains, SSO, pen-test) | Demo lite + honest README |
| Editing the golden playbook live from the UI | Use overrides / decision log |
| Hosted Railway/Vercel unless they ask | Zip + local is enough |
| Fake “GDPR certified” badges | Don’t lie |

Details: [01-PRD-MVP.md](01-PRD-MVP.md). How to build: [02-MVP-IMPLEMENTATION.md](02-MVP-IMPLEMENTATION.md).

---

## Success checklist

- [ ] Journey A works (sample + upload)  
- [ ] Flags cite playbook rules; “Needs human” when no fallback  
- [ ] Accept / Edit / Reject + history  
- [ ] Journey B demable  
- [ ] Journey C demable  
- [ ] Works with fake/offline AI mode  
- [ ] README: approach, data, security, limits, not legal advice  
- [ ] Short Loom  

---

## Plain-English jargon

| Word | Means |
|---|---|
| **Playbook** | JSON file of “how we usually negotiate” (caps, jurisdiction, etc.) |
| **Closed-book** | AI may only use the playbook + this contract — not invent policy |
| **Fence** | Wrap contract text in tags so the model treats it as data, not orders |
| **Prompt injection** | Hidden instructions inside a PDF to trick the AI |
| **Override** | Sarah says “this variation is actually OK” → stored for next time |

---

## Bottom line

**Upload → check playbook → flag/counter → decide → remember — with a basic shield against hostile PDFs.**

That’s the take-home. Vision docs are the sequel, not the homework.
