# RedlineGuard evals

Offline suites under `FAKE_LLM=1` (same defaults as the evaluator path in [`docs/13-HANDOFF.md`](../docs/13-HANDOFF.md)):

| Suite | What it checks |
|-------|----------------|
| `injection` | Hard cue halts; clean text does not |
| `adjudicate` | Hard → hold; ambiguous → auto-clear |
| `compare_l0` | California needle flags with semantic off |
| `draft_react` | ReAct Fake returns draft + ≤6-step trace |
| `pii_redact` | Email/phone placeholders |

```bash
cd RedlineGuard
set FAKE_LLM=1
set FAKE_EMBED=1
python -m evals.runners.run_all
```

Reports: `evals/reports/all_<ts>.json` and `evals/reports/latest.json`.

Smoke-only: `python -m evals.runners.run_smoke`.
