# Autodevelop Reflection — 2026-05-01

**Mission:** Reflect on the performance of the Autonomous Research
Infrastructure so far in order to improve on the functions/features.

**Span reflected on:** PRs #43–55 merged in the previous ~12 hours. 13
PRs, 274 tests at the end, every PR triggered by a specific production
failure observed in autonomous-loop runs.

---

## Anatomy of the 13-PR push

| Layer | PRs | What changed |
|---|---|---|
| LLM access | #43 | Real Anthropic model IDs (Scout was 400'ing on `claude-opus-4-6`) |
| Pipeline plumbing | #44, #46, #48 | Artifacts on disk, `Paper.status` terminal flips on every outcome, per-stage `asyncio.timeout` |
| Drafter quality | #51, #55 | Closed registered-source set; per-tier grouping with claim_type pairing rules |
| Verifier quality | #47, #50, #52, #53, #54 | claim_id matching → prompt completeness → batch 15→5→1→5; finally accept partial coverage as honest |
| L1 / L2 review | #45, #49, #54 | Soft-link recognition; topic-shaped vs type-shaped permissions; coverage formula honest |

End state: pipeline produces papers reliably, generation completes in ~22
min, papers reach `funnel_stage=candidate` end-to-end, L1 passes, L2
gates on real quality issues. Workflow exits poll loop cleanly within
the 45-min budget.

---

## Patterns observed

### 1. Tight feedback loop made the pipeline tractable

**Every PR triggered by a single concrete failure:**
- Run 25163518619 → `claude-opus-4-6` 400 → PR #43
- Run 25165943475 → status stuck at `draft` → PR #44
- Run 25167747205 → Designer hung 43 min → PR #46
- ...

Average ~30 min per PR. Each shipped with dedicated regression tests.
The discipline of "trigger one paper, observe, fix one thing" was much
more productive than "ship multiple speculative fixes, validate later".

### 2. Closed-set prompt design works (PR #51's pattern)

The single most successful prompt change was telling the LLM **the exact
list of valid IDs** and saying **"do not invent"**. Result: 0/25 →
25/25 claims hard-linked to registered sources.

PR #55 extended the same pattern to tier groupings (with pairing rules)
and resolved 14 spurious tier_violations.

**Generalizable principle:** When the LLM's output must satisfy a
registry constraint, present the registry **inline** in the prompt as a
closed list, not as nested context the LLM has to dig through.

### 3. "MUST output N entries" prompt language doesn't constrain LLM behavior

PRs #50 and #52 added "CRITICAL — output exactly N entries" language and
shrunk batches. The LLM kept cherry-picking. Empirical data:

| batch | claims sent | LLM returned | rate |
|---|---|---|---|
| 15 | 25 | 11 | 44% |
| 5 | 18 | 6 | 33% |
| 1 | 19 | 1 | 5% |

The LLM has a roughly fixed "comfortable response size" regardless of
input. Prompt engineering can't override this.

### 4. When you can't fix the LLM, fix the metric

PR #54's response: instead of fighting the LLM into 100% coverage,
**redefine coverage** to mean "Verifier completeness" (verified+failed)
rather than "verification pass rate" (verified only). Honest measurement
beat heroic engineering.

This reframing also exposed PR #55's necessary fix — once the L2
coverage check was honest, it stopped masking the tier_violation issue
underneath, and the fix shipped immediately.

### 5. The deploy-race trap

Twice (runs 25174825093 and 25187417178) I triggered validation immediately
after merge while Render's deploy was mid-rollout. Result: paper
created → Scout started → deploy killed the worker → paper stuck at
status=draft forever.

**Operational rule:** wait 15+ min after merge before triggering
validation. The 21-25 min wait between most successful validations was
not an accident.

### 6. Iterative observability compounds

Each PR that improved measurement exposed the next-deeper quality issue:
- Once `Paper.status` flipped on terminal states (#44), the workflow
  could exit cleanly → revealed the next failure mode (Designer hang).
- Once L1 accepted soft-linked claims (#45), it stopped firing CRITICAL
  on every paper → revealed the L2 tier_violation issue.
- Once L2's coverage formula was honest (#54) → revealed the Drafter's
  tier-blindness for empirical claims.

**Generalizable principle:** Don't treat observability fixes as
"non-functional". They are the highest-leverage work because they
unblock discovery of every subsequent issue.

---

## What's still unaddressed (by impact × confidence)

### A. Re-verify endpoint (HIGH leverage)

**Problem:** Verifier consistently leaves ~70% of claims at
`verification_status=pending`. PR #54 made this acceptable rather than
fixed. There's no way to ask "verify the pending ones again" — coverage
stays low forever for that paper.

**Fix:** POST /api/v1/papers/{paper_id}/re-verify. Runs Verifier only on
claims with status=pending. Multiple invocations approach 100% coverage
incrementally. Operationally, cron can sweep papers with high pending
count.

**Effort:** S (small). High-confidence fix because Verifier's existing
match-by-claim-id pipeline already handles the writeback correctly.

### B. Architectural CLAUDE.md (HIGH long-term value)

**Problem:** The system's design lives in commit messages and test
files. Future sessions (and future contributors) have to reverse-engineer
why things are the way they are.

**Fix:** Single CLAUDE.md at repo root documenting:
- Pipeline stages (Scout → Designer → Data Steward → Analyst → Drafter
  → Collegial → Verifier → Packager)
- The closed-source-set + tier-pairing prompt pattern
- Verifier's "honest partial coverage" design
- The deploy-race operational rule
- Where each PR lives in the architecture

**Effort:** S. Low risk.

### C. Stuck-paper reaper (MEDIUM)

**Problem:** 8+ papers from deploy-race incidents have
status=draft/funnel=idea forever. They distort metrics and may eventually
break tournament-pairing.

**Fix:** Admin endpoint that flips papers with `created_at > 1h ago AND
status='draft' AND last_heartbeat_at > 30m ago` to status=killed with
kill_reason="abandoned by worker (deploy race)".

**Effort:** S.

### D. Source registry expansion (MEDIUM)

**Problem:** 21 registered SourceCards is narrow for AI governance.
Many legal/regulatory authorities the LLM wants to cite (CFR sections,
court cases, OECD reports) aren't registered.

**Fix:** Add 20-30 more sources. Data work, not code.

**Effort:** M.

### E. Cost tracking (MEDIUM)

**Problem:** No per-paper cost accounting. As throughput scales, this
becomes a hard constraint.

**Fix:** Log token counts + estimated $ per LLM call. Add a /admin/papers/
{id}/cost endpoint.

**Effort:** M.

### F. L3-L5 review readiness audit (LOW confidence — depends on actual L2 pass)

**Problem:** No paper has yet survived L2 in production, so L3 (method
review) and L4 (adversarial) have never fired. Risk of latent bugs there.

**Fix:** Wait until a paper actually passes L2; then validate L3+ in
the next iteration cycle.

**Effort:** unclear — depends on what surfaces.

---

## Decision

Ship **A (re-verify endpoint)** as PR #56 alongside **B (CLAUDE.md)** as
PR #57. Together they:
- Unblock the most-fought-but-unsolved Verifier coverage gap
- Document the system's design so future sessions stand on solid ground

Skip the persona panels — production data from 13 PRs and 5+ validation
runs is more authoritative than simulated personas would be on this
specific codebase.
