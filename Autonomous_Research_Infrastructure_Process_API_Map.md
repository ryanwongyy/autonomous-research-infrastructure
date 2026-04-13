# Autonomous Research Infrastructure: Process and API Map

Date: 2026-04-13
Scope: Current `ProjectAPE Replica` implementation for the AI-governance domain

## Executive view

The current stack breaks into five API dependency layers:

1. `LLM generation APIs`
   Anthropic is the main generation engine. OpenAI is the main independent reviewer and judge. Google/Gemini is wired as an optional fallback.
2. `Public source-data APIs`
   The system can fetch governance evidence from public registries and research indexes.
3. `Internal product APIs`
   FastAPI endpoints expose review, tournament, provenance, release, throughput, novelty, and RSI operations.
4. `Local execution interfaces`
   Some critical steps are not external APIs at all: Python execution, Docker fallback, filesystem artifact storage, hashing, and optional `pdflatex`.
5. `Human approval interfaces`
   Release, significance memos, and final submission decisions still require human sign-off, even when earlier stages are automated.

## Process-to-API map

| Process | What the automation does | Main service/module | Internal trigger/API | External API required | Notes |
| --- | --- | --- | --- | --- | --- |
| Idea generation | Generates candidate research ideas for a paper family | `paper_generation/roles/scout.py` | Service-level orchestration in `run_full_pipeline()` | `Anthropic Messages API` | Uses the generation provider and family/source metadata to propose ideas. |
| Idea screening | Scores ideas on novelty, importance, data adequacy, credibility, venue fit, burden | `paper_generation/roles/scout.py` | Same orchestration path | `Anthropic Messages API` | Same provider as idea generation; scoring is recomputed locally after the model reply. |
| Research design creation | Produces a locked research design and design memo | `paper_generation/roles/designer.py` | Service-level orchestration | `Anthropic Messages API` | This is the lock-setting stage for downstream work. |
| Lock verification | Checks lock integrity and version consistency | `paper_generation/boundary_enforcer.py`, `storage/lock_manager.py` | Called throughout pipeline and review | `No external API` | Local hash and DB checks only. |
| Source manifest planning | Maps the locked design to source cards and fetch parameters | `paper_generation/roles/data_steward.py` | Service-level orchestration | `Anthropic Messages API` | LLM chooses which registered sources to query and how. |
| Source fetching and snapshotting | Pulls real source data, writes immutable snapshots, hashes artifacts | `paper_generation/roles/data_steward.py`, `data_sources/*` | Service-level orchestration | `Federal Register API`, `SEC EDGAR EFTS`, `Regulations.gov API`, `USAspending API`, `OpenAlex API`, `CourtListener API` | Actual live dependencies depend on which source cards the manifest selects. |
| Analysis code generation | Writes executable analysis code and requirements | `paper_generation/roles/analyst.py` | Service-level orchestration | `Anthropic Messages API` | Produces Python code plus expected outputs. |
| Analysis execution | Runs generated code and emits result objects | `paper_generation/roles/analyst.py` | Service-level orchestration | `No external API` | Uses local subprocess execution or Docker if available. |
| Manuscript drafting | Writes LaTeX manuscript and initial claim map | `paper_generation/roles/drafter.py` | Service-level orchestration | `Anthropic Messages API` | Also creates evidence-linked claim records in the DB. |
| Collegial review loop | Runs supportive multi-round colleague feedback and revision | `collegial/review_loop.py` | `POST /papers/{paper_id}/collegial-review` | `Anthropic Messages API` | Current implementation routes this through the generation provider. |
| Verifier role | Checks claims for evidence links, citation validity, causal language, tier compliance, scope | `paper_generation/roles/verifier.py` | Service-level orchestration | `Anthropic Messages API` | This is separate from the mechanical L1/L2 review pipeline. |
| L1 structural review | Checks artifacts, lock integrity, claim-map coverage, numbering, citations | `review_pipeline/l1_structural.py` | `POST /papers/{paper_id}/review` | `No external API` | Purely mechanical review with local files and DB state. |
| L2 provenance review | Verifies claims against source snapshots, source freshness, quote matching, tier rules | `review_pipeline/l2_provenance.py` | `POST /papers/{paper_id}/review`, `POST /papers/{paper_id}/claims/verify` | `No live external API during review` | Uses local snapshots and provenance records. It depends on earlier source-fetch APIs having already run. |
| L3 method review | Runs independent non-Claude methods review | `review_pipeline/l3_method.py` | `POST /papers/{paper_id}/review` | `OpenAI Chat Completions API` or `Google Gemini API` | Current code pins L3 to `gpt-4o`; Gemini is the coded fallback path. |
| L4 adversarial review | Runs alternative explanation, source fragility, and causal-language attacks | `review_pipeline/l4_adversarial.py` | `POST /papers/{paper_id}/review` | `OpenAI Chat Completions API` and `Anthropic Messages API` | This is the clearest dual-provider stage in the stack. |
| L5 human escalation | Generates a structured escalation report for a human reviewer | `review_pipeline/l5_human_escalation.py` | Triggered automatically inside review pipeline | `No external API` | Deliberately system-only. |
| Novelty detection | Compares designs against prior family papers | `novelty/detector.py` | `POST /papers/{paper_id}/novelty-check` | `Anthropic Messages API` for borderline semantic cases | First pass is local structural similarity; only borderline cases call an LLM. |
| Tournament matching | Builds family-local match batches with cross-source mixing | `tournament/matcher.py` | `POST /tournament/run` | `No external API` | Pure scheduling logic. |
| Tournament judging | Compares paper pairs with order swapping to reduce positional bias | `tournament/judge.py`, `tournament/engine.py` | `POST /tournament/run` | `OpenAI Chat Completions API` by default, optional `Google Gemini API`, Anthropic fallback | Judge router prefers non-Anthropic models to avoid self-preference on Claude-generated papers. |
| Rating update | Updates TrueSkill and Elo scores | `tournament/rating_system.py` | Tournament execution | `No external API` | Local math only. |
| Judge calibration | Tests judges on corrupted control variants | `tournament/judge_calibrator.py` | Service-level, RSI-adjacent | `OpenAI Chat Completions API` or configured judge provider | Uses the same judge channel as tournament evaluation. |
| Package assembly | Hashes artifacts, computes Merkle root, creates disclosure and contribution log | `paper_generation/roles/packager.py` | Service-level orchestration | `No external API` | Pure local packaging and cryptographic bookkeeping. |
| PDF compilation | Compiles LaTeX to PDF if available | `paper_generation/paper_composer.py` | Internal utility path | `No external API` | Requires local `pdflatex`, not a network service. |
| Release gating | Checks preconditions and transitions papers through internal/candidate/submitted/public | `release/release_manager.py` | `GET /papers/{paper_id}/release/*`, `POST /papers/{paper_id}/release/transition` | `No external API` | Depends on local review/package state and human approvals. |
| Significance memo | Records human editorial rationale for submit/hold/kill | `release/significance_memo_service.py` | `POST /papers/{paper_id}/significance-memo` | `No external API` | Human-authored input, stored internally. |
| Outcome tracking | Records real-world venue outcomes and computes acceptance rates | `outcomes/outcome_tracker.py` | `POST /papers/{paper_id}/outcomes` | `No external API` | Manual entry in current implementation. |
| Reliability tracking | Computes paper/family reliability metrics | `reliability/reliability_engine.py` | `GET /reliability/*` | `No external API` | Local metrics from existing artifacts and reviews. |
| Failure taxonomy | Auto-classifies failures from review outputs | `failure_taxonomy/classifier.py` | Triggered after failed reviews | `No external API` | Local rule-based classification. |
| Throughput planning | Computes daily targets, queue priorities, and annual projections | `throughput/batch_scheduler.py`, `throughput/funnel_tracker.py` | `GET /throughput/*` | `No external API` | Planning layer over DB pipeline state. |
| RSI prompt optimization | Proposes prompt patches from failures | `rsi/role_prompt_optimizer.py`, `rsi/review_prompt_sharpener.py` | `POST /rsi/tier1*/*` | `Anthropic Messages API`, sometimes `OpenAI` depending on target | Self-improvement begins here. |
| RSI family/config tuning | Optimizes family configs, drift thresholds, and reviewer weights | `rsi/family_config_optimizer.py`, `rsi/drift_tuner.py`, `rsi/policy_calibrator.py` | `POST /rsi/tier2*/*` | Primarily `Anthropic Messages API` | Uses local metrics plus model-generated proposals. |
| RSI architecture changes | Proposes layer/role splits, merges, bypasses, and taxonomy expansion | `rsi/layer_architect.py`, `rsi/role_architect.py`, `rsi/family_discoverer.py`, `rsi/taxonomy_expander.py` | `POST /rsi/tier3*/*` | `Anthropic Messages API` with occasional judge-side checks | Higher-risk self-modification layer. |
| RSI meta-pipeline | Runs self-improvement cycles across tiers | `rsi/meta_pipeline.py` | `POST /rsi/tier4c/start-cycle` and related endpoints | `Anthropic Messages API`, `OpenAI` for judge-related loops | The broadest automation layer in the stack. |

## Public data APIs currently implemented

These are the live source clients currently present in the backend:

| Source ID | API | Key required | Main use in AI governance |
| --- | --- | --- | --- |
| `federal_register` | Federal Register API | No | Rules, notices, executive actions, agency publications |
| `edgar` | SEC EDGAR EFTS | No | Corporate disclosure, board oversight, governance statements |
| `regulations_gov` | Regulations.gov API v4 | Yes | Rulemaking dockets, comments, consultation trails |
| `usaspending` | USAspending API | No | Public procurement, federal awards, vendors, state capacity |
| `openalex` | OpenAlex API | No key, but email/polite pool supported | Literature scanning, benchmarks, novelty context |
| `courtlistener` | CourtListener API v4 | Yes | Litigation, judicial opinions, enforcement signals |

## LLM/API stack by function

| Function | Default provider | Why |
| --- | --- | --- |
| Generation pipeline | Anthropic (`claude-opus-4-6`, `claude-sonnet-4-6`) | Main writing, design, drafting, and verification engine |
| Independent method review | OpenAI (`gpt-4o`) | Explicit non-Claude independence requirement |
| Tournament judging | OpenAI (`gpt-4o`) by default | Reduces provider self-preference when judging Claude outputs |
| Optional judge fallback | Google (`gemini-2.0-flash`) if key exists | Wired for future native PDF-friendly judging |
| Borderline novelty check | Anthropic via generation provider | Used only when structural similarity is inconclusive |

## APIs not yet automated but likely needed in a fuller production stack

These are not required by the current codebase, but they are the obvious next APIs if the infrastructure matures beyond the present prototype:

- `Crossref API` or `Semantic Scholar API`
  Better citation metadata, DOI normalization, and reference graph checks.
- `ORCID API`
  Cleaner author identity and contributor workflows for human sign-off.
- `GitHub API`
  Better release packaging, artifact publication, and issue-based human escalation.
- `Cloud object storage API`
  If the artifact store moves beyond local filesystem storage.
- `Journal submission system integrations`
  If submission is automated rather than manually recorded.
- `Observability APIs`
  If you want cost, latency, and failure telemetry per stage in production.

## Minimum API stack to run the current system credibly

If the goal is a serious but lean operating version of the current architecture, the minimum external API stack is:

- `Anthropic API`
  Required for almost all generation stages.
- `OpenAI API`
  Required for independent method review and preferred tournament judging.
- `Federal Register API`
  Core regulatory evidence source.
- `SEC EDGAR`
  Core corporate governance evidence source.
- `USAspending API`
  Core procurement/state-capacity evidence source.
- `OpenAlex API`
  Core literature and benchmark context source.

Then add these when the relevant paper families need them:

- `Regulations.gov API`
- `CourtListener API`
- `Google Gemini API` as an optional judge/review fallback

## Practical implication for budgeting

Most automated processes do **not** require their own separate paid API.
The main paid dependencies are concentrated in:

- `Anthropic`
- `OpenAI`
- optionally `Google Gemini`
- optionally key-gated public-data sources like `Regulations.gov` and `CourtListener`

Most of the rest of the system is local orchestration, database state, storage, hashing, subprocess execution, and human editorial control.
