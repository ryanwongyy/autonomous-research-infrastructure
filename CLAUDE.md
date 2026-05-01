# ARI — Architecture & Operations Notes for Claude Code

This file is the canonical reference for working on the Autonomous
Research Infrastructure (ARI) codebase. It documents the design
decisions, operational patterns, and gotchas distilled from PRs
#42–56 (Apr 30 – May 1, 2026). Read this before making changes; it
saves the 10-20 minutes that would otherwise go to reverse-engineering
from commit messages and tests.

---

## What ARI does

Generates AI-governance research papers end-to-end via an 8-stage
LLM pipeline, then runs a 5-layer review pipeline on each. The output
is a `Paper` row with status `candidate` (passed review), `killed`
(verifier-rejected or stage-failed), or `error` (uncaught exception).

## High-level pipeline

```
                     ┌──────────────────────────────────────┐
                     │ run_full_pipeline (orchestrator.py)  │
                     │ runs each stage in its own DB session│
                     └──────────────────┬───────────────────┘
                                        ▼
   Scout → Designer → Data Steward → Analyst → Drafter → Collegial → Verifier → Packager
   (idea  (lock      (source        (analysis (manuscript (revision (claim     (final
   gen)   artifact)  manifest)      code)     LaTeX)      review)   verify)    package)

                                        ▼
                          Review pipeline (separately triggered)
                          L1 structural → L2 provenance → L3 method →
                          L4 adversarial → L5 human escalation
```

## Stage timeouts (orchestrator.py:_STAGE_TIMEOUT_SEC)

| Stage | Timeout | Rationale |
|---|---|---|
| scout | 600s | 5 idea-gen + 5 screening calls |
| designer | 300s | 1 LLM call ~30s |
| data_steward | 600s | LLM + N HTTP fetches |
| analyst | 900s | LLM + Python subprocess |
| drafter | 900s | 32K-token manuscript |
| collegial_review | 600s | 3 colleagues x 2 rounds + assessor |
| verifier | 600s | N batches of 5 claims |
| packager | 60s | DB+filesystem only (should be <1s) |

These are wrapped via `async with asyncio.timeout(...)` in the two
stage-runner helpers. On timeout, the wrapper returns `{"status":
"failed", "wrapper_timeout": True, ...}` rather than raising, so the
caller's contract holds (every wrapper call returns a dict).

## Paper.status terminal flips

The cron poll loop watches `Paper.status` for terminal values:

```
candidate | published | error | killed | rejected
```

The orchestrator MUST flip to one of these on every outcome,
otherwise the workflow times out at 45 min:

| Outcome | status | helper |
|---|---|---|
| Pipeline completes (Packager done) | `candidate` | inline (orchestrator.py) |
| Verifier recommends `reject` | `killed` | inline |
| Stage returns `failed` (e.g. wrapper timeout) | `killed` | `_set_killed_at_stage` |
| Uncaught exception | `error` | `_set_error` |

Without the stage-failed branch (added in PR #48), papers stuck at
`status=draft` indefinitely if any stage failed.

## Storage layout per paper

Packager writes to `<settings.papers_dir>/<paper_id>/package_v1/`:

```
package_v1/
├── manuscript.tex          (Drafter output)
├── code/analysis.py        (Analyst output)
├── data/manifest.json      (source manifest)
└── results/results.json    (analyst result manifest)
```

The Paper row's `paper_tex_path` / `code_path` / `data_path` columns
point at these files. L1 structural review reads those columns
directly — they MUST be populated or L1 fires CRITICAL
`artifact_missing`.

---

## LLM patterns that work

### Closed-set source picking (Drafter, PR #51)

When the LLM's output must satisfy a registry constraint (e.g. claim's
`source_ref` must be a registered SourceCard ID), present the registry
**inline** as a closed list:

```
REGISTERED SOURCE CARDS (the ONLY valid source_ref values when
source_type="source_span"):
  - SC_USASPENDING (USAspending.gov)
  - SC_FEDERAL_REGISTER (Federal Register / GovInfo)
  ...

Do NOT invent source IDs. If a claim genuinely needs a source not
in the registered list, narrow the claim or drop it.
```

Result on production paper apep_8f5c16b6: 25/25 claims hard-linked.
Before this fix, papers had ~0 hard-linked and ~21 soft-linked
(LLM invented source names like "29 CFR § 1607.4(d)").

### Tier-grouped listings + pairing rules (Drafter, PR #55)

Extending the closed-set pattern: when the LLM also has to make a
*type* decision (claim_type) bound to the source choice, group the
listings by the relevant axis and explicitly state the pairing rules:

```
TIER A — primary, audited; SUITABLE for empirical/doctrinal:
  ...
TIER C — auxiliary; ONLY for descriptive/historical (NEVER as the
anchor of an empirical claim — that's a CRITICAL tier_violation).
```

### claim_id matching for writeback (Verifier, PR #47)

When the LLM returns N entries that must be matched back to N input
items, give each input a numeric `claim_id`, ask the LLM to echo it,
and match by id (with text as fallback). Never rely on the LLM to
echo input text verbatim — paraphrasing breaks text-equality matching.

## LLM patterns that DON'T work

### "MUST output exactly N entries" prompt language

PRs #50/52 added "CRITICAL — output exactly N entries" instructions
and shrunk batches from 15 → 5. The LLM still cherry-picked.
Empirical data:

| batch | claims sent | LLM returned |
|---|---|---|
| 15 | 25 | 11 (44%) |
| 5 | 18 | 6 (33%) |
| 1 | 19 | 1 (5%, regressed) |

The LLM has a roughly fixed "comfortable response size" regardless
of input. Prompt engineering can't override this. Per-claim
verification (batch=1) actually regressed — the prompt becomes
mostly context with little task and the LLM behaves differently,
or Anthropic rate-limits rapid sequential calls.

### When you can't fix the LLM, fix the metric

PR #54: the L2 review's `coverage_ratio` was `verified / total`. This
conflated "Verifier processed it" with "claim passed verification".
A paper with 20 verified + 5 failed (real quality) was indistinguishable
from one with 20 unverified + 5 verified (Verifier completeness gap).

New formula: `coverage_ratio = (verified + failed) / total` (Verifier
completeness). `pass_rate = verified / (verified + failed)` is now a
separate field. Quality issues surface via `failed` count and
`tier_violations`, not via degraded coverage.

### Re-verify endpoint for incremental coverage (PR #56)

Since the LLM cherry-picks regardless of prompt/batch, the right
remedy is operational: `POST /admin/papers/{id}/re-verify` runs
Verifier on `pending`-only claims. Repeated invocations approach
100% coverage. Useful from a cron sweep over papers with high
pending counts.

---

## Database conventions

### Per-stage sessions, never long-running

Each pipeline stage runs in its own `async with async_session() as s:`
block. Postgres' `idle_in_transaction_session_timeout` kills
long-running idle transactions; a session held across multiple LLM
calls (each ~10-30 sec) hits this limit and `commit()` raises
`InterfaceError`.

The orchestrator has two helper variants:
- `_run_stage_with_session`: short stages (<2 min), session held across
  read+work+commit.
- `_run_stage_no_outer_session`: long-LLM stages (Analyst, Drafter,
  Verifier). The wrapper opens NO session; the stage manages its own
  read → LLM → write phases internally.

### TIMESTAMP WITHOUT TIME ZONE columns

Several tables (e.g. `paper_packages`, `claim_maps.verified_at`) use
TIMESTAMP WITHOUT TIME ZONE on Postgres. asyncpg refuses to silently
strip tzinfo. Use `app.utils.utcnow_naive()` (returns `datetime.now()`
without tzinfo), not `datetime.now(timezone.utc)`.

Production failure: run #25140027480 hit DataError on a
`PaperPackage.created_at` write because the value was tz-aware.

### Heartbeats

Each stage writes a heartbeat (`paper.last_heartbeat_at` +
`last_heartbeat_stage`) at start. Used by:
- Diagnostic: when a paper is stuck, the heartbeat tells you which
  stage was last active.
- Reaper logic (future): papers with old heartbeats and non-terminal
  status are deploy-race orphans.

---

## Operational rules

### Deploy-race rule

Wait **15+ minutes** after merging to main before triggering an
autonomous-loop validation. Render's deploy takes 5-10 min and a
paper created mid-rollout will have its background task killed,
leaving `status=draft, funnel_stage=idea` forever.

Bitten twice (runs 25174825093 and 25187417178). Two papers per
incident were stranded.

### Workflow poll budget

`autonomous-loop.yml` polls `paper.status` every 30s for up to 45
min. If paper.status doesn't reach a terminal value in 45 min, the
workflow times out (but the background task may still be running).
Generation takes 17-29 min normally, so this is loose enough.

If you see a 45-min timeout, the bug is almost always in
`Paper.status` not being flipped — one of the orchestrator's terminal-
state writes is missing.

### Validation pattern that works

1. Trigger run via `gh workflow run autonomous-loop.yml -f count=1`
2. Watch with Monitor on a poll loop checking `gh run view --json
   status,conclusion,jobs`
3. After completion, GET /api/v1/papers/{id} for paper state and
   /api/v1/papers/{id}/provenance for claim-level breakdown
4. If anything failed, GET /api/v1/papers/{id}/reviews for L1/L2 details

This pattern surfaces specific paper IDs and concrete claim
breakdowns within 30 min of triggering.

---

## Testing conventions

### Source-inspection tests over integration

For orchestrator and stage-helper changes, use `inspect.getsource()`
+ string assertions. Reason: the orchestrator's helpers open their
own DB sessions via `async_session()` from `app.database`, which
points at the production-configured DB (not the test in-memory
SQLite). Integration tests would hit the wrong DB.

Pattern: `assert 'paper.status = "candidate"' in src` to lock in
that a specific code path exists.

### Regression tests are mandatory

Every PR fixing a production failure must add at least one
regression test that fails without the fix. Tests should reference
the production paper ID in their docstring (e.g. "production paper
apep_8f5c16b6 had ...") so the failure mode is grounded in real
data.

### Lint config

Backend uses `ruff check` and `ruff format`. The CI gate runs both.
`pyproject.toml` configures the rule selection — ruff config there
is the source of truth.

---

## File map (key paths)

```
backend/
├── app/
│   ├── api/
│   │   ├── batch.py          # POST /batch/generate-async (cron entrypoint)
│   │   ├── papers.py         # GET /papers/*, POST /admin/papers/{id}/re-verify
│   │   ├── provenance.py     # GET /papers/{id}/provenance
│   │   └── reviews.py        # GET /papers/{id}/reviews
│   ├── services/
│   │   ├── paper_generation/
│   │   │   ├── orchestrator.py            # run_full_pipeline + stage wrappers
│   │   │   └── roles/
│   │   │       ├── scout.py
│   │   │       ├── designer.py
│   │   │       ├── data_steward.py
│   │   │       ├── analyst.py
│   │   │       ├── drafter.py             # closed source set + tier pairing
│   │   │       ├── collegial/review_loop.py
│   │   │       ├── verifier.py            # batch=5, status_filter param
│   │   │       └── packager.py            # writes artifacts to disk
│   │   ├── review_pipeline/
│   │   │   ├── l1_structural.py           # accepts source_span_ref as link
│   │   │   ├── l2_provenance.py
│   │   │   ├── l3_method.py
│   │   │   └── l4_adversarial.py
│   │   ├── provenance/
│   │   │   ├── claim_verifier.py          # coverage = (verified+failed)/total
│   │   │   └── source_registry.py         # topic vs type permission shape
│   │   └── llm/
│   │       └── router.py                  # reads settings.claude_opus_model
│   ├── config.py             # 8 model-id settings (env-overridable)
│   └── models/
│       ├── paper.py          # status, funnel_stage, paper_tex_path, etc.
│       ├── claim_map.py      # verification_status, source_card_id, etc.
│       └── source_card.py    # tier, claim_permissions (topic-shaped data)
└── tests/                    # mostly source-inspection tests for orchestrator;
                              # integration tests for L1/L2 review and pure
                              # helpers
```

---

## Recent PR history (#42 → #56)

The `git log --oneline main` is the source of truth, but as a quick
overview of design intent:

- **#42–43**: Pipeline plumbing fixed (wrappers never raise, real model IDs)
- **#44–46**: Observability infrastructure (artifacts on disk, terminal
  status flips, per-stage timeout)
- **#47–55**: Iterative LLM-quality work — Verifier matching, prompt
  shaping, batch-size experiments (15→5→1→5), Drafter source picking
  + tier awareness, L1/L2 honest measurement
- **#56**: Operational composition — re-verify endpoint as the missing
  step for incremental Verifier coverage

Reflection on this push: `.claude/autodevelop-reflection-2026-05-01.md`.

---

## When making changes

1. Read this file (you're already doing it).
2. If touching the orchestrator, run `pytest tests/test_long_running_pipeline.py
   tests/test_wrappers_never_raise.py tests/test_per_stage_timeout.py
   tests/test_orchestrator_paper_status.py tests/test_stage_failure_terminal_status.py`
   — these lock in the contracts.
3. If touching Verifier or L1/L2, also run
   `tests/test_verifier_*.py tests/test_l*_*.py`.
4. Run the full gate (`pytest tests/ -q && ruff check app/ tests/`)
   before pushing.
5. After CI green and merge, **wait 15 min** before triggering
   validation against Render (deploy-race rule).

When validating in production:
- Use `gh workflow run autonomous-loop.yml -f count=1`
- Wait for the Monitor task to fire DONE
- Inspect the most recent paper via the API endpoints
- The `funnel_stage`, `last_heartbeat_stage`, and `error_message`
  fields tell you where it landed

When papers stack up at status=draft (deploy-race victims), the
re-verify endpoint won't help. Future work: build a reaper that
flips orphans to status=killed. Tracking: not yet implemented.
