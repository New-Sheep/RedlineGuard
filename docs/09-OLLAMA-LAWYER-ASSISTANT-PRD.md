# Local Ollama lawyer assistant (post-MVP PRD)

| | |
|---|---|
| **Purpose** | Spec for narrow local-LLM co-pilots beyond the take-home core |
| **Audience** | Builders implementing Ollama / NVIDIA co-pilots |
| **Status** | Active enhancement track |
| **Last updated** | 2026-07-19 |
| **Related** | [`01-PRD-MVP.md`](01-PRD-MVP.md) (core scope) · [`08-COMPARE-ALGORITHM-AUDIT.md`](08-COMPARE-ALGORITHM-AUDIT.md) · [`07-MVP-AUDIT-CHECKPOINT.md`](07-MVP-AUDIT-CHECKPOINT.md) |

**Authority:** [`01-PRD-MVP.md`](01-PRD-MVP.md) owns Must/Should for the take-home. This file owns the lawyer-assistant layer. Product principle wins on conflict.

**Product principle (unchanged):** *AI proposes. The playbook decides. The lawyer confirms.*

---

## 1. Executive summary

Turn RedlineGuard from “playbook checker + draft stub” into a **local lawyer’s assistant**: a small set of **narrow Ollama agents** that read text, understand meaning against *company* rules and *prior decisions*, and help Sarah set up, review, rewrite, remember, and brief - without becoming a free-form chat bot.

**Runtime:** Ollama on the lawyer’s machine (`FAKE_LLM=0`). Offline demos stay on `FAKE_LLM=1` with deterministic stubs.

**One-line promise:** 
*Local model assists every step of the loop - setup, judge, draft, explain memory, brief - always closed-book and human-gated.*

---

## 2. Why this sprint

### 2.1 Already shipped (baseline)

| Capability | Status | Code anchors |
|---|---|---|
| Needs-human **draft** via Ollama | Done | `apps/core/llm.py`, `drafting.py` |
| Compare **L0 + L1** (rules + local embed) | Done | `apps/review/services/compare/` |
| Compare **L2 LLM judge** | Done (candidate judge; see [`08`](08-COMPARE-ALGORITHM-AUDIT.md)) | `layer_llm.py` |
| Decision memory (retrieve → prefer Accept) | Done (LLM explainer is this PRD) | Chroma / SQLite precedents |
| Playbook propose (PDF / starter) | Done via bootstrap (Fake or live LLM) | `playbook_bootstrap.py` |
| Cloud HTTP LLM | Available via `LLM_PROVIDER` | Optional |

### 2.2 Gap this PRD closes

Sarah still feels “tool,” not “assistant,” in:

1. **Setup** - Fake proposes rules; Ollama should draft real starter playbooks 
2. **Rewrite** - One draft; no co-pilot options or “why” 
3. **Memory** - Precedents fire silently; no plain-English “why this one” 
4. **Close-out** - No cover note / decision brief after a review 
5. **Learning gaps** - Rejects don’t propose new rules for Activate 
6. **Diligence stretch** - L2 only judges existing candidates; no bounded discovery 

### 2.3 Non-goals (still Won’t)

| Won’t | Why |
|---|---|
| Open chat with the full PDF | Wrong product; injection + hallucination |
| Free ReAct multi-tool agent loop | Vision only; insecure demo surface |
| Auto-mutate golden playbook from Accept/Reject | Governance: Activate only |
| Silent “AI risk” with no rule id | Breaks trust |
| Requiring cloud LLM | Ollama-first; Fake always works |
| Claiming legal correctness | Assistant only |

---

## 3. Agent architecture (local)

Think **tools with schemas**, not a chatbot.

```text
┌─────────────────────────────────────────────────────────────────┐
│ Sarah (human gate) │
│ Activate · Accept/Edit/Reject · Override · Unlearn │
└────────────────────────────▲────────────────────────────────────┘
 │ structured proposals only
┌────────────────────────────┴────────────────────────────────────┐
│ Ollama agents (this PRD) │
│ ProposePlaybook · Judge(L2) · Draft · RewriteCopilot │
│ MemoryExplain · DecisionBrief · GapSuggest · Discover(opt) │
└────────────────────────────▲────────────────────────────────────┘
 │ fenced excerpts + allowlists
┌────────────────────────────┴────────────────────────────────────┐
│ Deterministic core (MVP) │
│ SecurityGate · L0/L1 compare · Memory retrieve · Playbook JSON │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Shared contract for every agent

| Rule | Requirement |
|---|---|
| **Input minimize** | Clause excerpt / rule slice / finding list - not whole untrusted PDF when avoidable |
| **Fence** | Untrusted text in `<untrusted_…>` (or equivalent); system prompt ignores commands inside |
| **Schema out** | Pydantic / `llm_json`; drop or Fake-fallback on parse failure |
| **Closed-book** | Only cite playbook rule ids / prior decision ids that were supplied in context |
| **Fake path** | Every agent has a `FAKE_LLM=1` stub so Loom works offline |
| **Audit** | Log `agent`, `model`, `latency_ms`, `prompt_hash` (lite), `fake|ollama` |

### 3.2 Config (env)

| Key | Role |
|---|---|
| `FAKE_LLM` | `1` = stubs; `0` = Ollama |
| `OLLAMA_HOST` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT` | Shared engine |
| Per-agent toggles | `LLM_JUDGE`, `LLM_PLAYBOOK_PROPOSE`, `LLM_REWRITE_COPILOT`, `LLM_MEMORY_EXPLAIN`, `LLM_DECISION_BRIEF`, `LLM_GAP_SUGGEST`, `LLM_DISCOVER` (default: on when `FAKE_LLM=0` except Discover off) |

---

## 4. Features (Must / Should / Could)

### F1 - Ollama playbook propose (**Must**)

**Job:** Replace Fake-only bootstrap with local LLM that proposes editable rules from a playbook PDF or 3-5 past contracts.

| | |
|---|---|
| **Agent** | `ProposePlaybook` |
| **In** | Fenced sanitized extract(s); optional existing golden as “style hint” (not auto-merge) |
| **Out** | List of proposed rules: `id`, `clause_type`, `preferred`, `hard_ceiling`, `fallback_text?`, `severity`, `rationale` |
| **Gate** | Lawyer edits → **Activate** (unchanged). Never write golden without Activate. |
| **UI** | Import / Starter flows: badge “Proposed by Ollama” vs Fake; keep halt on poisoned PDF |
| **Fake** | Keep current deterministic proposal for offline |

**Acceptance:** With `FAKE_LLM=0` and Ollama up, PDF import and starter each produce ≥3 valid Pydantic rules; Activate still required; security halt still blocks Activate.

---

### F2 - Rewrite co-pilot (**Must**)

**Job:** On Rewrite, Sarah gets explanation + multiple negotiation tones - not a single opaque draft.

| | |
|---|---|
| **Agent** | `RewriteCopilot` |
| **In** | Fenced `clause_excerpt`, rule preferred/ceiling/fallback, optional memory hit, current draft |
| **Out** | `why` (≤3 sentences), `options[]` with `tone` ∈ {`firm`, `soft`, `fallback`}, `text`, `cites_rule_id` |
| **Gate** | Sarah picks / edits → Accept / Edit / Reject as today |
| **UI** | Rewrite screen: Why strip + 2-3 option cards; selecting one fills the editor |
| **Fake** | One option from fallback or canned why |

**Acceptance:** Needs-human and fallback paths both show Why; at least two tones when Ollama succeeds; Edit still works on chosen text.

---

### F3 - Memory enhancement (**Must**)

Memory already **retrieves** precedents. This feature makes memory **legible and smarter** with Ollama - without inventing policy.

#### F3a - “Why this precedent” explainer (**Must**)

| | |
|---|---|
| **Agent** | `MemoryExplain` |
| **When** | Draft path uses a memory hit, **or** Memory / Rewrite UI shows a precedent |
| **In** | Current clause excerpt, rule id, top-k precedent snippets + decision labels |
| **Out** | One plain sentence: why this precedent fits (or why it was skipped) |
| **UI** | Chip / callout under draft: “Reusing Accept from *…* because …” |
| **Fake** | Template string from decision label + rule id |

#### F3b - Memory-aware draft ranking (**Must**)

| | |
|---|---|
| **Job** | When multiple precedents match, Ollama ranks which Accept to prefer (or warn if nearby Reject) |
| **In** | Same as retrieval candidates + clause excerpt |
| **Out** | `chosen_precedent_id`, `confidence`, `warn_reject_nearby?: bool`, `explain` |
| **Constraint** | May only choose from supplied ids; never invent text as “from memory” if not in corpus |
| **Fake** | First Accept by existing score order |

#### F3c - Decision → memory enrichment (**Should**)

| | |
|---|---|
| **When** | After Accept / Edit / Reject |
| **Agent** | `MemoryEnrich` (optional async) |
| **Out** | Short `summary` + `tags[]` stored on precedent for better future retrieve / UI |
| **Constraint** | Does not change playbook; Unlearn still deletes the row |

#### F3d - Memory hygiene assist (**Could**)

| | |
|---|---|
| **Job** | Suggest Unlearn / merge when two precedents conflict on same rule |
| **Out** | Advisory list only; Sarah confirms Unlearn |

**Acceptance (Must slice):** Every memory-sourced draft shows an explainer; ranking never cites an id not in the candidate set; `FAKE_LLM=1` still demos Journey B.

---

### F4 - Decision brief / cover note (**Should**)

**Job:** After a review (or on demand from Review), produce a short lawyer-facing brief Sarah can paste into email / ticket.

| | |
|---|---|
| **Agent** | `DecisionBrief` |
| **In** | Finding list (rule ids, severities, statuses), optional decisions so far, playbook titles |
| **Out** | `subject`, `body_markdown` (bullets: flags, asks, overrides) - closed-book |
| **UI** | “Copy brief” on Review / History detail |
| **Fake** | Bullet list template from findings |

**Acceptance:** Brief only mentions rule ids present in input; Copy works; no claim of legal advice (footer disclaimer).

---

### F5 - Thin-playbook gap suggestions (**Should**)

**Job:** From repeated Rejects / manual “Needs human” gaps, **propose** new or tightened rules for Activate - never silent-write.

| | |
|---|---|
| **Agent** | `GapSuggest` |
| **In** | Aggregated decisions (rule_id, action, edited text samples), active playbook ids |
| **Out** | Proposed rule patches / new rules + rationale |
| **UI** | Playbook page: “Suggested from your decisions” → opens proposal → Activate path |
| **Fake** | 0-1 canned suggestion from fixtures |

**Acceptance:** Suggestions are clearly “Proposed”; cannot become golden without Activate.

---

### F6 - Bounded discovery (**Could** / stretch)

**Job:** After L0∪L1, optionally ask Ollama which **existing** playbook rule ids might apply to keyword-hot segments that produced no finding.

| | |
|---|---|
| **Agent** | `Discover` |
| **In** | Segment excerpts + **allowlist** of active rule ids + short rule summaries |
| **Out** | Candidate `{rule_id, excerpt_ref, confidence}` - then run through existing L2 judge / draft path |
| **Constraint** | May only emit ids from allowlist; default **off** |
| **Fake** | No-op |

**Acceptance:** With Discover on, no finding cites a rule id absent from active playbook.

---

### F7 - Harden existing Ollama paths (**Must** - hygiene)

| Item | Requirement |
|---|---|
| Draft excerpt-only | Confirm drafts never send full contract when clause span exists |
| Judge audit | Surface `llm` source + confirmed/dropped in Review breakdown (already partial) |
| `manage.py check_ollama` | Documented in README for this sprint |
| Side-by-side Fake vs Ollama | DEBUG-only toggle or env - optional Should |

---

## 5. Priority / build order

| Sprint slice | Features | Demo story |
|---|---|---|
| **A - Setup + hygiene** | F1, F7 | “Ollama wrote our starter playbook; I Activated” |
| **B - Daily review feel** | F2, F3a, F3b | “Why + tones + memory explains itself” |
| **C - Close the loop** | F4, F3c | “Copy brief; memory tags next time” |
| **D - Stretch** | F5, F6, F3d | Gaps + discovery + hygiene |

Recommended default ship for Loom: **A + B**. C/D if time.

---

## 6. User journeys (additions)

### Journey D - Ollama playbook onboarding

1. Empty playbook → Starter or Import PDF 
2. Processing: security → **ProposePlaybook (Ollama)** 
3. Edit proposed rules → Activate 
4. Upload contract → real flags cite activated rules 

### Journey E - Assisted rewrite

1. Open finding → Rewrite 
2. See Why + firm/soft/fallback options (Ollama) 
3. Pick / edit → Accept 
4. Memory stores decision; next similar shows MemoryExplain 

### Journey F - Memory-aware second pass

1. Second similar contract 
2. Draft prefers prior Accept; UI shows “because …” 
3. If Reject nearby, warn chip before Accept 

### Journey G - Decision brief

1. Finish review (or mid-queue) 
2. Copy brief → paste to counsel / requester 

---

## 7. UX requirements

1. Always label source: **Fake** vs **Ollama** vs **Playbook fallback** vs **Memory** 
2. Never present proposed playbook rules as Active without Activate chrome 
3. Memory explainer is visible wherever a precedent drives the draft 
4. Rewrite options are selectable cards, not hidden in JSON 
5. Brief includes “Not legal advice” one-liner 
6. Processing steps name agents when they run (“Proposing playbook…”, “Judging flags…”, “Drafting options…”) 
7. Calm institutional tone - no chatbot bubble UI for these agents 

---

## 8. Security & privacy

Same bar as MVP, applied to **every new agent**:

1. Sanitize + fence untrusted text 
2. Structured output validation 
3. Minimize prompt contents (excerpts) 
4. Poisoned playbook PDF still **halts**; ProposePlaybook must not run to Activate 
5. Document in README: *what leaves the machine* when `FAKE_LLM=0` (local Ollama only - no cloud unless user later enables HTTP client) 
6. Optional Should: crude PII redact before prompt 

---

## 9. Data & persistence

| Artifact | Change |
|---|---|
| Precedent / memory row | Add optional `summary`, `tags`, `explain_cached` (F3c / F3a cache) |
| Playbook import | Store `proposal_source`: `fake` \| `ollama`, `model` |
| Finding / draft | Store `draft_options` JSON optional; `memory_explain` string |
| Audit log (lite) | JSONL or table: agent calls for Loom trust story |
| Env / settings | Per-agent toggles (section 3.2) |

No change to golden playbook write path except via existing Activate.

---

## 10. API / service seams (implementation hints)

Keep Django service functions; shared `OllamaEngine` + `llm_json`.

| Agent | Suggested module |
|---|---|
| ProposePlaybook | `apps/review/services/playbook_bootstrap.py` (swap Fake → Ollama impl) |
| RewriteCopilot | `apps/review/services/rewrite_copilot.py` (new) |
| MemoryExplain / rank | `apps/review/services/memory_assist.py` (new) |
| MemoryEnrich | hook from decision save |
| DecisionBrief | `apps/review/services/decision_brief.py` (new) |
| GapSuggest | `apps/review/services/gap_suggest.py` (new) |
| Discover | `apps/review/services/compare/layer_discover.py` (new, optional) |
| Judge / Draft | already exist - harden only |

UI: extend Rewrite + Memory + Playbook + Review templates; no new “Chat” screen.

---

## 11. Testing

| Layer | Cases |
|---|---|
| Unit | Each agent: Fake stub shape; Ollama mocked HTTP → valid Pydantic; reject unknown rule ids |
| Unit | MemoryExplain never cites missing precedent id |
| Unit | Discover allowlist enforcement |
| Integration | `FAKE_LLM=1` full Journey A/B/D/E without Ollama |
| Manual | `FAKE_LLM=0` + `check_ollama` + one live Propose + Rewrite + MemoryExplain |

---

## 12. Success metrics (demo / take-home)

| Metric | Target |
|---|---|
| Loom stories | Setup (F1) + Rewrite+Memory (F2/F3) without cloud |
| Closed-book | 0 flags / drafts citing invented rule ids in tests |
| Offline | Full UI path on Fake |
| Latency | Per-agent soft budget &lt; 30s on 7B-8B local model for demo excerpts |
| Governance | 0 golden writes without Activate in code paths |

---

## 13. Open questions

1. Cache MemoryExplain on the draft row vs recompute each Rewrite view? 
2. Store RewriteCopilot options on Finding or generate on page load? 
3. GapSuggest: batch nightly vs “Suggest now” button? 
4. Default model pin: document `qwen2.5:7b-instruct` vs `llama3.1:8b` in README for this machine class? 

---

## 14. Summary checklist

| ID | Feature | Priority | Ollama? |
|---|---|---|---|
| F1 | Playbook propose | Must | Yes |
| F2 | Rewrite co-pilot (why + tones) | Must | Yes |
| F3a | Memory “why this precedent” | Must | Yes |
| F3b | Memory-aware ranking / Reject warn | Must | Yes |
| F3c | Decision → summary/tags enrich | Should | Yes |
| F3d | Conflict / Unlearn suggestions | Could | Yes |
| F4 | Decision brief | Should | Yes |
| F5 | Gap → proposed rules | Should | Yes |
| F6 | Bounded discovery | Could | Yes |
| F7 | Harden drafts + audit + docs | Must | - |

**Bottom line:** Build a **local multi-agent assistant** as thin, fenced Ollama calls on the existing loop - especially **memory that explains and ranks** - not a chat REPL. Start with **F1 + F2 + F3a/b + F7**.
