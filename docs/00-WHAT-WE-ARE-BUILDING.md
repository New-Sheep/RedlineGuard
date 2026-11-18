# What are we building?

**Purpose:** Plain-English product orientation. Scope law lives in [`01-PRD-MVP.md`](01-PRD-MVP.md).

---

## One sentence

**RedlineGuard** helps an in-house lawyer upload a routine contract, check it against the company’s written rules (a **playbook**), see what doesn’t match, get a suggested rewrite when the playbook allows one, and Accept / Edit / Reject so the next similar contract is easier.

**Principle:** AI proposes. The playbook decides. The lawyer confirms.

---

## Who it is for

**Sarah**, a lawyer inside PortSwigger (in-house, not a law firm). Queue of mutual NDAs and small order forms. Same redlines keep coming back. She needs a **first-pass co-pilot**.

---

## AI as a multiplier

1. Rules live in a **playbook file** (governance changes without rewriting the app)
2. The model judges **against that playbook** (closed-book)
3. Sarah’s Accept / Edit / Reject (and optional override) **feeds the next review**

**Setup when the playbook is empty:** empty state → upload a playbook PDF or past contracts → AI proposes rules → Sarah reviews and **Activates**. Only then do reviews produce real flags.

---

## The loop

```
(If no playbook: empty state → propose → Activate)
Upload PDF (or sample)
    → Security: treat text as untrusted (clean + fence before AI)
    → Compare to playbook_config.json
    → Flagged bits + which rule they broke
    → Suggest rewrite if playbook has fallback text; else Needs human
    → Accept / Edit / Reject
    → Remember (decision history and/or playbook override)
```

Also demable: hostile sample that tries to trick the AI → Security alert. Poisoned playbook PDF → halt before Activate.

---

## Screens

Visuals: [`designs/`](../designs/) (Upload → Processing → Review → Rewrite).

| Screen | Job |
|---|---|
| Upload | File or sample |
| Processing | Reading → security → playbook compare |
| Review | Contract + flags (each cites a playbook rule) |
| Rewrite | Original vs suggested; Accept / Edit / Reject |
| Security alert | Hostile / injection-style input |
| History | Past decisions |
| Playbook | Active rules + setup (import → Activate) |

---

## Demo journeys

| Journey | Show |
|---|---|
| **A** | Sample → playbook flags → rewrite → Accept |
| **B** | Prior Accept reused in draft, and/or Override respected next run |
| **C** | Hostile sample → Security alert |
| **E** | Empty playbook → propose → Activate → Journey A works |

---

## MVP focus (in scope)

Playbook-cited first-pass review, lite security halt, decision memory / overrides, local zip or GitHub + venv delivery, Fake/offline fallback when needed. Post-MVP co-pilots: [`09-OLLAMA-LAWYER-ASSISTANT-PRD.md`](09-OLLAMA-LAWYER-ASSISTANT-PRD.md). Future multi-agent vision: [`15-LANGGRAPH-MULTI-AGENT-ARCHITECTURE.md`](15-LANGGRAPH-MULTI-AGENT-ARCHITECTURE.md).

---

## Jargon

| Word | Means |
|---|---|
| **Playbook** | Company’s written negotiation rules |
| **Activate** | Lawyer confirms a proposed playbook; only then it is live |
| **Closed-book** | AI uses the playbook + this contract only |
| **Fence** | Wrap contract text so the model treats it as data |
| **Override** | Lawyer marks a variation OK; stored for next time |

---

## Next reads

[`01-PRD-MVP.md`](01-PRD-MVP.md) · [`06-PRODUCT-MAP.md`](06-PRODUCT-MAP.md) · [`13-HANDOFF.md`](13-HANDOFF.md) · [`../README.md`](../README.md)
