"""Layer 2: Provenance Verification Review

Checks every citation against cached source, every quote string-matched,
every data object resolved to source card + transform chain.
"""

from __future__ import annotations

import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.review import Review
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.services.provenance.claim_verifier import verify_paper_claims
from app.services.provenance.source_registry import (
    SNAPSHOT_FRESHNESS_DAYS,
)

logger = logging.getLogger(__name__)


async def run_provenance_review(session: AsyncSession, paper_id: str) -> Review:
    """Run Layer 2 provenance verification.

    Checks:
    1. Every central citation checked against cached source span
    2. Every direct quote string-matched against source text
    3. Every data object resolves to source card + snapshot
    4. Source tier compliance: no Tier C source anchoring central claims
    5. Source freshness: no claims based on stale snapshots
    6. Source hash drift: flag if source changed since snapshot

    Uses claim_verifier.verify_paper_claims() as the core engine.

    Returns Review with stage='l2_provenance'.
    """
    paper = await _load_paper(session, paper_id)
    if paper is None:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=None,
            verdict="fail",
            severity="critical",
            issues=[
                {
                    "check": "paper_exists",
                    "severity": "critical",
                    "message": f"Paper '{paper_id}' not found.",
                }
            ],
            content="Provenance review aborted: paper not found.",
        )

    issues: list[dict] = []

    # ------------------------------------------------------------------
    # Core check: use claim_verifier to verify all paper claims
    # ------------------------------------------------------------------
    claim_report = await verify_paper_claims(session, paper_id)

    # Map claim_verifier results to issues.
    if claim_report["total_claims"] == 0:
        issues.append(
            {
                "check": "no_claims",
                "severity": "critical",
                "message": "No claims found for this paper. Cannot verify provenance.",
            }
        )

    # 1. Unlinked claims (citations not backed by cached source).
    for unlinked in claim_report.get("unlinked_claims", []):
        issues.append(
            {
                "check": "citation_unlinked",
                "severity": "critical",
                "message": f"Claim not linked to any source: {unlinked}",
            }
        )

    # 4. Source tier violations (Tier C anchoring central claims).
    for violation in claim_report.get("tier_violations", []):
        issues.append(
            {
                "check": "tier_violation",
                "severity": "critical",
                "message": violation.get("violation", "Source tier violation"),
                "claim_id": violation.get("claim_id"),
                "source_card_id": violation.get("source_card_id"),
                "source_tier": violation.get("source_tier"),
            }
        )

    # 5. Stale source snapshots.
    for stale in claim_report.get("stale_sources", []):
        issues.append(
            {
                "check": "source_stale",
                "severity": "warning",
                "message": (
                    f"Source snapshot {stale.get('snapshot_id')} is "
                    f"{stale.get('days_stale')} days old "
                    f"(threshold: {SNAPSHOT_FRESHNESS_DAYS} days)."
                ),
                "claim_id": stale.get("claim_id"),
                "source_card_id": stale.get("source_card_id"),
                "days_stale": stale.get("days_stale"),
            }
        )

    # Failed verifications.
    if claim_report.get("failed", 0) > 0:
        issues.append(
            {
                "check": "verification_failures",
                "severity": "critical",
                "message": (f"{claim_report['failed']} claim(s) failed verification."),
            }
        )

    # Pending verifications (not yet verified).
    if claim_report.get("pending", 0) > 0:
        issues.append(
            {
                "check": "verification_pending",
                "severity": "warning",
                "message": (f"{claim_report['pending']} claim(s) still pending verification."),
            }
        )

    # ------------------------------------------------------------------
    # 2. Direct quote string-matching
    # ------------------------------------------------------------------
    quote_issues = await _check_direct_quotes(session, paper_id, paper)
    issues.extend(quote_issues)

    # ------------------------------------------------------------------
    # 3. Data object resolution (every claim with result_object_ref)
    # ------------------------------------------------------------------
    data_issues = await _check_data_object_resolution(session, paper_id)
    issues.extend(data_issues)

    # ------------------------------------------------------------------
    # 6. Source hash drift
    # ------------------------------------------------------------------
    drift_issues = await _check_source_hash_drift(session, paper_id)
    issues.extend(drift_issues)

    # ------------------------------------------------------------------
    # Coverage ratio check
    # ------------------------------------------------------------------
    # PR #54 redefined coverage_ratio as (verified + failed) / total —
    # i.e. Verifier process completeness, NOT verification pass rate.
    # The intent (per CLAUDE.md): quality issues surface via the
    # `verification_failures` and `tier_violations` checks above;
    # coverage just measures whether the Verifier reached every claim.
    #
    # Production paper apep_82532feb (autonomous-loop run 25289671965)
    # exposed an inconsistency: L2 still fired CRITICAL `coverage_incomplete`
    # at coverage < 0.8 even though the LLM cherry-picks claims (documented
    # behavior — see "MUST output exactly N entries" in CLAUDE.md). With
    # ~30-50% verdict rate per Verifier batch, no single workflow run can
    # reach 80% coverage; only repeated cron re-verify (PR #56) drives it
    # up over hours. Failing the L2 check on coverage essentially
    # guaranteed every paper would fail L2 on its first review pass.
    #
    # PR #73: downgrade `coverage_incomplete` to warning at all coverage
    # levels. The redundant `verification_pending` warning above already
    # surfaces the pending count for operator awareness. Real quality
    # issues remain CRITICAL (verification_failures, tier_violations).
    coverage = claim_report.get("coverage_ratio", 0.0)
    if coverage < 1.0 and claim_report["total_claims"] > 0:
        issues.append(
            {
                "check": "coverage_incomplete",
                "severity": "warning",
                "message": (
                    f"Verifier coverage is {coverage:.1%} "
                    f"({claim_report['verified'] + claim_report['failed']}/"
                    f"{claim_report['total_claims']}). "
                    f"Cron re-verify will fill in pending claims over time."
                ),
            }
        )

    # ------------------------------------------------------------------
    # Determine verdict
    # ------------------------------------------------------------------
    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")

    if critical_count > 0:
        verdict = "fail"
        max_severity = "critical"
    elif warning_count > 0:
        verdict = "revision_needed"
        max_severity = "warning"
    else:
        verdict = "pass"
        max_severity = "info"

    # Build summary.
    summary_parts = [
        f"Provenance review completed: {len(issues)} issue(s) found.",
        f"  Coverage: {coverage:.1%} "
        f"({claim_report.get('verified', 0)}/{claim_report.get('total_claims', 0)})",
        f"  Critical: {critical_count}, Warning: {warning_count}",
    ]
    if verdict == "pass":
        summary_parts.append("All provenance checks passed.")
    else:
        for issue in issues:
            summary_parts.append(
                f"  [{issue['severity'].upper()}] {issue['check']}: {issue['message']}"
            )

    return await _create_review(
        session,
        paper_id=paper_id,
        family_id=paper.family_id,
        verdict=verdict,
        severity=max_severity,
        issues=issues,
        content="\n".join(summary_parts),
    )


# ---------------------------------------------------------------------------
# Sub-checks
# ---------------------------------------------------------------------------


async def _check_direct_quotes(session: AsyncSession, paper_id: str, paper: Paper) -> list[dict]:
    """Check that direct quotes in claims can be string-matched against source text.

    For each claim that has a source_span_ref, verify that the claim text
    (or a quoted portion of it) appears within the referenced source snapshot.
    """
    issues: list[dict] = []

    stmt = select(ClaimMap).where(
        ClaimMap.paper_id == paper_id,
        ClaimMap.source_span_ref.isnot(None),
        ClaimMap.source_snapshot_id.isnot(None),
    )
    result = await session.execute(stmt)
    claims_with_spans: list[ClaimMap] = list(result.scalars().all())

    for claim in claims_with_spans:
        # Extract quoted text from the claim (text between quotation marks).
        quoted_fragments = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', claim.claim_text)
        if not quoted_fragments:
            continue  # No direct quotes to check.

        # Load the source snapshot content for string matching.
        snapshot = await _load_snapshot(session, claim.source_snapshot_id)
        if snapshot is None:
            issues.append(
                {
                    "check": "quote_snapshot_missing",
                    "severity": "warning",
                    "message": (
                        f"Cannot verify quotes in claim {claim.id}: "
                        f"snapshot {claim.source_snapshot_id} not found."
                    ),
                    "claim_id": claim.id,
                }
            )
            continue

        # Try to load snapshot content from artifact store.
        snapshot_text = await _load_snapshot_text(snapshot)
        if snapshot_text is None:
            issues.append(
                {
                    "check": "quote_snapshot_unreadable",
                    "severity": "warning",
                    "message": (
                        f"Cannot read snapshot content for claim {claim.id}: "
                        f"snapshot path '{snapshot.snapshot_path}' not accessible."
                    ),
                    "claim_id": claim.id,
                }
            )
            continue

        # Check each quoted fragment.
        for fragment in quoted_fragments:
            # Normalize whitespace for matching.
            normalized_fragment = " ".join(fragment.split())
            normalized_source = " ".join(snapshot_text.split())

            if normalized_fragment.lower() not in normalized_source.lower():
                issues.append(
                    {
                        "check": "quote_mismatch",
                        "severity": "critical",
                        "message": (
                            f"Direct quote in claim {claim.id} not found in source: "
                            f"'{fragment[:80]}...'"
                        ),
                        "claim_id": claim.id,
                        "quote_fragment": fragment[:200],
                    }
                )

    return issues


async def _check_data_object_resolution(session: AsyncSession, paper_id: str) -> list[dict]:
    """Check that every claim with a result_object_ref actually resolves.

    Verifies that the referenced result object has a valid structure and
    points to an identifiable analysis run.
    """
    issues: list[dict] = []

    stmt = select(ClaimMap).where(
        ClaimMap.paper_id == paper_id,
        ClaimMap.result_object_ref.isnot(None),
    )
    result = await session.execute(stmt)
    claims_with_results: list[ClaimMap] = list(result.scalars().all())

    for claim in claims_with_results:
        try:
            ref = json.loads(claim.result_object_ref)
        except (json.JSONDecodeError, TypeError):
            issues.append(
                {
                    "check": "result_ref_invalid_json",
                    "severity": "critical",
                    "message": (f"Claim {claim.id} has malformed result_object_ref JSON."),
                    "claim_id": claim.id,
                }
            )
            continue

        # Check that the reference has the expected structure.
        required_fields = {"analysis_run_id", "table"}
        missing_fields = required_fields - set(ref.keys())
        if missing_fields:
            issues.append(
                {
                    "check": "result_ref_incomplete",
                    "severity": "warning",
                    "message": (
                        f"Claim {claim.id} result_object_ref missing fields: "
                        f"{sorted(missing_fields)}"
                    ),
                    "claim_id": claim.id,
                    "missing_fields": sorted(missing_fields),
                }
            )

    return issues


async def _check_source_hash_drift(session: AsyncSession, paper_id: str) -> list[dict]:
    """Flag claims where the source content hash has changed since the snapshot.

    Compares SourceCard.content_hash (latest) against the SourceSnapshot.snapshot_hash
    that the claim references.
    """
    issues: list[dict] = []

    stmt = select(ClaimMap).where(
        ClaimMap.paper_id == paper_id,
        ClaimMap.source_card_id.isnot(None),
        ClaimMap.source_snapshot_id.isnot(None),
    )
    result = await session.execute(stmt)
    claims: list[ClaimMap] = list(result.scalars().all())

    # Cache source card lookups to avoid redundant queries.
    source_cache: dict[str, SourceCard | None] = {}
    snapshot_cache: dict[int, SourceSnapshot | None] = {}

    for claim in claims:
        # Load source card.
        if claim.source_card_id not in source_cache:
            sc_stmt = select(SourceCard).where(SourceCard.id == claim.source_card_id)
            sc_result = await session.execute(sc_stmt)
            source_cache[claim.source_card_id] = sc_result.scalar_one_or_none()

        source_card = source_cache[claim.source_card_id]
        if source_card is None:
            continue

        # Load snapshot.
        if claim.source_snapshot_id not in snapshot_cache:
            sn_stmt = select(SourceSnapshot).where(SourceSnapshot.id == claim.source_snapshot_id)
            sn_result = await session.execute(sn_stmt)
            snapshot_cache[claim.source_snapshot_id] = sn_result.scalar_one_or_none()

        snapshot = snapshot_cache[claim.source_snapshot_id]
        if snapshot is None:
            continue

        # Compare hashes.
        if (
            source_card.content_hash
            and snapshot.snapshot_hash
            and source_card.content_hash != snapshot.snapshot_hash
        ):
            issues.append(
                {
                    "check": "source_hash_drift",
                    "severity": "warning",
                    "message": (
                        f"Source '{source_card.name}' content has changed since "
                        f"snapshot {snapshot.id} was taken. "
                        f"Snapshot hash: {snapshot.snapshot_hash[:16]}..., "
                        f"current hash: {source_card.content_hash[:16]}..."
                    ),
                    "claim_id": claim.id,
                    "source_card_id": source_card.id,
                    "snapshot_id": snapshot.id,
                }
            )

    return issues


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_snapshot(session: AsyncSession, snapshot_id: int | None) -> SourceSnapshot | None:
    if snapshot_id is None:
        return None
    stmt = select(SourceSnapshot).where(SourceSnapshot.id == snapshot_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_snapshot_text(snapshot: SourceSnapshot) -> str | None:
    """Try to load snapshot text content from the artifact store path."""
    if not snapshot.snapshot_path:
        return None
    try:
        import aiofiles

        async with aiofiles.open(snapshot.snapshot_path) as f:
            return await f.read()
    except (FileNotFoundError, ImportError, UnicodeDecodeError):
        return None


async def _create_review(
    session: AsyncSession,
    *,
    paper_id: str,
    family_id: str | None,
    verdict: str,
    severity: str,
    issues: list[dict],
    content: str,
) -> Review:
    """Create and persist a Layer 2 Review record."""
    review = Review(
        paper_id=paper_id,
        stage="l2_provenance",
        model_used="system",
        verdict=verdict,
        content=content,
        severity=severity,
        resolution_status="open" if verdict != "pass" else "resolved",
        family_id=family_id,
        review_rubric_version="provenance_v1",
        issues_json=json.dumps(issues),
    )
    session.add(review)
    await session.flush()
    logger.info(
        "[%s] L2 provenance review: verdict=%s, issues=%d",
        paper_id,
        verdict,
        len(issues),
    )
    return review
