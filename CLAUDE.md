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

### Verifier source excerpts (PR #65)

Production paper apep_b4680e6e was a doctrinal law paper with 25
Tier-A claims sourced from CourtListener (federal court decisions)
and Federal Register. L1 PASSED. But the Verifier left 23 of 25
claims at `pending` because its prompt only included source IDs
and tier metadata — no actual case text. The LLM correctly refused
to assess "Court X held Y" without reading the underlying decision.

PR #65 fixes this: `_load_source_excerpts` reads the most recent
SourceSnapshot for each cited source_card_id, truncates to a sane
size (~2K chars per source), and includes the content in the
Verifier prompt. Best-effort: missing files are noted but don't
abort. The prompt explicitly tells the LLM "do not refuse on
grounds of haven't read the source — the excerpt is provided."

This was the unlock for non-zero verified counts. apep_9afaf116
became the first paper post-#65 with `verified > 0` (5 of 25).

### Drafter empirical→result_object pairing (PR #66)

apep_5bd06118 was killed by Verifier reject (11/25 claims failed)
because empirical claims like "Pre-treatment trends are parallel"
were anchored via `source_type=source_span` to data sources like
`edgar`. EDGAR has filings, not statistical findings. Verifier
correctly flagged the mismatch.

PR #66 adds an explicit rule to the Drafter prompt:
- `claim_type=empirical` → `source_type=result_object` (Analyst output)
- `claim_type=descriptive`/`doctrinal` → `source_type=source_span`
  (text in the source itself)

Plus a Phase-3 diagnostic that counts `empirical+source_span`
violations and logs WARNING. Drafter does NOT raise — Verifier
catches downstream.

### Drafter framing directive when Analyst fails (PR #67)

apep_9afaf116 had its Analyst stage fail (`unterminated string
literal`), so result_objects was empty. PR #66's claim-level rule
correctly re-typed individual claims, but the abstract still
framed the paper as completed empirical work: "we employ a
difference-in-differences design to estimate the causal effect."
The Verifier (PR #65) caught the claim-level mismatch but cannot
catch a paper-level falsehood — the abstract has no claim_id.

PR #67 adds a `FRAMING DIRECTIVE` block at the top of the Drafter
prompt that switches based on whether result_objects exist:

- Results present: permissive ("you may report findings").
- No results: forbids "we find / we estimate / we show / the
  coefficient on / the treatment effect is" framing entirely;
  provides three concrete reframings (research design, doctrinal
  analysis, framework-building).

Phase-3 diagnostic scans the manuscript for forbidden phrases
when no result_objects exist; logs WARNING with violation count.
Validated locally against apep_9afaf116's manuscript: detects 4
violations (2 abstract + 1 conclusion + 1 elsewhere).

### Drafter claim_text source-defensibility (PR #68)

In apep_9afaf116's 5 verified vs 11 failed claims, the dividing
line was NOT claim_type or source_type — those rules from PRs
#55/66 were followed in many failed claims. The dividing line
was claim_text *content*: VERIFIED claims described what the
source IS ("The Federal Register is the official daily
publication ..."), FAILED claims described the world via the
source ("Federal agencies deploy AI systems for consequential
public functions" with `source=usaspending` — USAspending has
spending records, not narrative claims).

PR #68 adds a CRITICAL section to the Drafter prompt with the
verified/failed examples named verbatim and the remediation
rule: claim_text must describe either (a) the source's own
content/structure or (b) a specific cited work within the
source. Do NOT assert world-facts via a database that merely
contains records.

### Analyst syntax-validate + retry (PR #69)

apep_9afaf116 wasted ~30s on a subprocess that failed with
`SyntaxError: unterminated string literal`. The LLM produced 16K
characters of Python with one missing closing quote — exactly
the kind of one-character mistake an LLM can correct from a
clear error.

PR #69 adds:
- `_validate_python_syntax(code)` — `compile()`-based check that
  runs in microseconds before the subprocess.
- `SYNTAX_RETRY_PROMPT` — sends the broken code + SyntaxError
  back to the LLM and asks for a fix scoped to syntax only.
- One retry. If the retry also fails, the broken code falls
  through to the existing ANALYSIS_ERROR path so PR #67's
  framing directive can still reframe the paper as research-
  design. No escalation to hard stage failure.

### Source registry expansion (PR #70)

Added 5 Tier A sources to close gaps observed in production:
`federal_ai_use_cases` (EO 13960 agency inventories — the
canonical answer to "what AI does the federal government use"),
`gao_reports`, `whitehouse_ostp`, `uspto_patents`, `arxiv`.

After PR #51's closed-set design, registry membership IS the
constraint. Expanding the registry directly reduces fabrication
without prompt growth — a different lever from prompt tuning,
useful when prompt accretion plateaus.

Tier A: 9 → 14. Total registry: 18 → 23.

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

## Recent PR history (#42 → #70)

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
- **#57–61**: Architecture docs (CLAUDE.md), manuscript durability
  (manuscript_latex column survives Render redeploy), reaper for
  orphaned papers, kill_reason exposure on Paper API
- **#62**: Batch re-verify endpoint + cron integration (autonomous
  loop sweeps papers with high pending count)
- **#63**: Analyst environment fix (`sys.executable`, numpy/pandas/scipy)
- **#64**: LLM retry — list+`extend()` pattern, retry_if_exception
  (lambda) so providers can mutate the retry set at module load
- **#65**: Verifier sees source excerpts so doctrinal claims verify
- **#66**: Drafter empirical→result_object pairing
- **#67**: Drafter framing directive forbids "we find" with no results
- **#68**: Drafter claim_text must describe source, not world via source
- **#69**: Analyst compile()-validate + retry on SyntaxError
- **#70**: Source registry +5 Tier A AI-governance sources

Reflection on PRs #43–55: `.claude/autodevelop-reflection-2026-05-01.md`.

The cumulative effect of #65–70: a layered defense against the
specific failure modes seen in apep_9afaf116. PR #65/#69 try to
recover; PR #66/#67/#68 ensure the paper is honest if recovery
fails; PR #70 widens the source set so the LLM doesn't have to
fabricate.

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
