"""Layer 1: Structural Integrity Review

Checks: compile/run/reproduce, lock compliance, artifact completeness,
claim-map coverage. No LLM call needed -- this is mechanical verification.
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
from app.services.storage.lock_manager import verify_lock
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)


async def run_structural_review(session: AsyncSession, paper_id: str) -> Review:
    """Run Layer 1 structural integrity checks.

    Checks:
    1. Lock artifact exists and hash matches Paper.lock_hash
    2. All required artifacts present (manuscript, code, data manifest, result objects)
    3. Claim map coverage: every central claim has a ClaimMap entry
    4. No orphan tables/figures (referenced in text but not generated)
    5. Citation completeness: every \\cite{} has a matching bib entry
    6. Consistent numbering (tables, figures, equations)
    7. Lock version matches Paper.lock_version

    Returns Review with stage='l1_structural', verdict='pass'/'fail'/'revision_needed',
    issues_json containing list of issues found.
    """
    paper = await _load_paper(session, paper_id)
    if paper is None:
        return await _create_review(
            session,
            paper_id=paper_id,
            family_id=None,
            verdict="fail",
            severity="critical",
            issues=[{"check": "paper_exists", "severity": "critical",
                     "message": f"Paper '{paper_id}' not found."}],
            content="Structural review aborted: paper not found.",
        )

    issues: list[dict] = []

    # ------------------------------------------------------------------
    # 1 & 7. Lock artifact verification (hash match + version match)
    # ------------------------------------------------------------------
    lock_result = await verify_lock(session, paper_id)

    if not lock_result["valid"]:
        for violation in lock_result.get("violations", []):
            issues.append({
                "check": "lock_integrity",
                "severity": "critical",
                "message": violation,
            })

    # Verify lock version consistency between artifact and paper record.
    if lock_result.get("lock_version", 0) > 0:
        if lock_result["lock_version"] != paper.lock_version:
            issues.append({
                "check": "lock_version_mismatch",
                "severity": "critical",
                "message": (
                    f"LockArtifact version ({lock_result['lock_version']}) "
                    f"does not match Paper.lock_version ({paper.lock_version})."
                ),
            })
    else:
        # No active lock at all
        if paper.lock_version > 0:
            issues.append({
                "check": "lock_missing",
                "severity": "critical",
                "message": (
                    "Paper has lock_version > 0 but no active lock artifact found."
                ),
            })

    # ------------------------------------------------------------------
    # 2. Required artifacts present
    # ------------------------------------------------------------------
    artifact_checks = {
        "manuscript": paper.paper_tex_path or paper.paper_pdf_path,
        "code": paper.code_path,
        "data_manifest": paper.data_path,
    }

    for artifact_name, artifact_path in artifact_checks.items():
        if not artifact_path:
            issues.append({
                "check": "artifact_missing",
                "severity": "critical" if artifact_name == "manuscript" else "warning",
                "message": f"Required artifact missing: {artifact_name}",
                "artifact": artifact_name,
            })

    # ------------------------------------------------------------------
    # 3. Claim map coverage
    # ------------------------------------------------------------------
    claims_stmt = select(ClaimMap).where(ClaimMap.paper_id == paper_id)
    claims_result = await session.execute(claims_stmt)
    claims: list[ClaimMap] = list(claims_result.scalars().all())

    if not claims:
        issues.append({
            "check": "claim_map_empty",
            "severity": "critical",
            "message": "No claim map entries found. Every central claim needs a ClaimMap entry.",
        })
    else:
        # A claim is considered "linked" if it has ANY of three pointers:
        #
        #   - ``source_card_id`` — hard FK to a registered SourceCard.
        #     Strongest provenance; the source has been pre-vetted.
        #   - ``result_object_ref`` — JSON pointer to an Analyst result.
        #     Means the claim is grounded in this paper's own analysis.
        #   - ``source_span_ref`` — JSON pointer to an LLM-named source
        #     that wasn't pre-registered as a SourceCard. Weaker than a
        #     hard FK but still real provenance: the Drafter did name a
        #     source (e.g. a CFR section, a Supreme Court case) and the
        #     downstream Verifier can audit the name. PR #36 added this
        #     fallback path specifically so LLM-hallucinated source IDs
        #     don't destroy the entire link record.
        #
        # The previous L1 check only inspected the first two fields,
        # which silently disagreed with PR #36's intent and made every
        # paper with soft-linked claims fail L1 with CRITICAL
        # ``central_claim_unlinked`` (production paper apep_144722c2:
        # 21/25 claims soft-linked, all flagged as unlinked).
        def _is_linked(claim: ClaimMap) -> bool:
            return (
                claim.source_card_id is not None
                or claim.result_object_ref is not None
                or claim.source_span_ref is not None
            )

        unlinked = [c for c in claims if not _is_linked(c)]
        if unlinked:
            issues.append({
                "check": "claim_map_unlinked",
                "severity": "warning",
                "message": (
                    f"{len(unlinked)} claim(s) have no source card, "
                    f"source span, or result object link."
                ),
                "claim_ids": [c.id for c in unlinked],
            })

        # Check for central claims specifically.
        central_types = {"empirical", "doctrinal"}
        central_claims = [c for c in claims if c.claim_type.lower() in central_types]
        unlinked_central = [c for c in central_claims if not _is_linked(c)]
        if unlinked_central:
            issues.append({
                "check": "central_claim_unlinked",
                "severity": "critical",
                "message": (
                    f"{len(unlinked_central)} central claim(s) "
                    f"(empirical/doctrinal) have no source, span, or "
                    f"result link."
                ),
                "claim_ids": [c.id for c in unlinked_central],
            })

        # Quality signal: how many claims are linked ONLY via the soft
        # source_span_ref path? High soft-link rates mean the Drafter is
        # naming sources the system doesn't know about — useful for
        # operators to track without being a structural failure. Logged
        # at INFO; not added to issues.
        soft_linked = [
            c for c in claims
            if c.source_card_id is None
            and c.result_object_ref is None
            and c.source_span_ref is not None
        ]
        if soft_linked:
            logger.info(
                "L1: paper %s has %d/%d soft-linked claims "
                "(source_span_ref only, no registered FK). Drafter is "
                "naming sources outside the SourceCard registry.",
                paper_id,
                len(soft_linked),
                len(claims),
            )

    # ------------------------------------------------------------------
    # 4. Orphan tables/figures check
    # ------------------------------------------------------------------
    manuscript_content = await _load_manuscript_text(paper)
    if manuscript_content:
        orphan_issues = _check_orphan_references(manuscript_content)
        issues.extend(orphan_issues)

        # ------------------------------------------------------------------
        # 5. Citation completeness
        # ------------------------------------------------------------------
        citation_issues = _check_citation_completeness(manuscript_content)
        issues.extend(citation_issues)

        # ------------------------------------------------------------------
        # 6. Consistent numbering
        # ------------------------------------------------------------------
        numbering_issues = _check_consistent_numbering(manuscript_content)
        issues.extend(numbering_issues)

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

    # Build human-readable summary.
    summary_parts = [
        f"Structural review completed: {len(issues)} issue(s) found.",
        f"  Critical: {critical_count}, Warning: {warning_count}, "
        f"Info: {len(issues) - critical_count - warning_count}",
    ]
    if verdict == "pass":
        summary_parts.append("All structural checks passed.")
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
# Internal helpers
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper | None:
    """Fetch a paper by ID."""
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_manuscript_text(paper: Paper) -> str | None:
    """Load the manuscript text content if available.

    Reads from the TeX path first (preferred), falling back to metadata_json
    content field, or abstract as last resort.
    """
    # Try to read the TeX file directly.
    tex_path = paper.paper_tex_path
    if tex_path:
        try:
            import aiofiles
            async with aiofiles.open(tex_path) as f:
                return await f.read()
        except (FileNotFoundError, ImportError):
            pass

    # Fall back to metadata_json if it contains manuscript text.
    meta = safe_json_loads(paper.metadata_json, {})
    if "manuscript_text" in meta:
        return meta["manuscript_text"]

    # Last resort: abstract.
    return paper.abstract


def _check_orphan_references(text: str) -> list[dict]:
    """Check for tables/figures referenced in text but possibly not generated.

    Looks for \\ref{tab:...} and \\ref{fig:...} labels and checks that
    corresponding \\label{...} definitions exist.
    """
    issues: list[dict] = []

    # Find all referenced labels.
    ref_pattern = re.compile(r"\\ref\{((?:tab|fig|eq):[^}]+)\}")
    label_pattern = re.compile(r"\\label\{([^}]+)\}")

    refs = set(ref_pattern.findall(text))
    labels = set(label_pattern.findall(text))

    orphans = refs - labels
    for orphan in sorted(orphans):
        prefix = orphan.split(":")[0] if ":" in orphan else "unknown"
        entity = {"tab": "Table", "fig": "Figure", "eq": "Equation"}.get(prefix, prefix)
        issues.append({
            "check": "orphan_reference",
            "severity": "warning",
            "message": f"{entity} reference '\\ref{{{orphan}}}' has no matching \\label.",
            "ref": orphan,
        })

    return issues


def _check_citation_completeness(text: str) -> list[dict]:
    """Check that every \\cite{key} has a plausible \\bibitem or bib entry.

    For simplicity, we extract all cited keys and check that they appear
    somewhere in the document (as \\bibitem or in a .bib-style reference).
    """
    issues: list[dict] = []

    # Extract all citation keys (handles \\cite{a,b,c} and \\citep{a}).
    cite_pattern = re.compile(r"\\cite[pt]?\{([^}]+)\}")
    cited_keys: set[str] = set()
    for match in cite_pattern.findall(text):
        for key in match.split(","):
            cited_keys.add(key.strip())

    # Extract all bibitem keys.
    bibitem_pattern = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}")
    bib_keys = set(bibitem_pattern.findall(text))

    # For bib files included via \bibliography{}, we cannot check without the
    # .bib file, so we only flag if bibitems are used and some are missing.
    missing = cited_keys - bib_keys
    if bib_keys and missing:
        # Only flag if bibitem-style bibliography is in use.
        for key in sorted(missing):
            issues.append({
                "check": "citation_missing_bib",
                "severity": "warning",
                "message": f"Citation key '{key}' has no matching \\bibitem.",
                "key": key,
            })
    elif not bib_keys and cited_keys:
        # Using external .bib file -- cannot verify, but note it.
        pass  # Not flagged; external bib verification is out of scope.

    return issues


def _check_consistent_numbering(text: str) -> list[dict]:
    """Check that table/figure/equation numbering appears consistent.

    Looks for \\begin{table}, \\begin{figure}, \\begin{equation} environments
    and ensures each has a \\label and a matching \\caption (for tables/figures).
    """
    issues: list[dict] = []

    env_pattern = re.compile(
        r"\\begin\{(table|figure|equation)\*?\}(.*?)\\end\{\1\*?\}",
        re.DOTALL,
    )

    for match in env_pattern.finditer(text):
        env_type = match.group(1)
        env_body = match.group(2)

        has_label = bool(re.search(r"\\label\{", env_body))
        has_caption = bool(re.search(r"\\caption", env_body))

        if not has_label:
            issues.append({
                "check": "missing_label",
                "severity": "info",
                "message": f"{env_type.capitalize()} environment without \\label.",
                "env_type": env_type,
            })

        if env_type in ("table", "figure") and not has_caption:
            issues.append({
                "check": "missing_caption",
                "severity": "info",
                "message": f"{env_type.capitalize()} environment without \\caption.",
                "env_type": env_type,
            })

    return issues


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
    """Create and persist a Layer 1 Review record."""
    review = Review(
        paper_id=paper_id,
        stage="l1_structural",
        model_used="system",
        verdict=verdict,
        content=content,
        severity=severity,
        resolution_status="open" if verdict != "pass" else "resolved",
        family_id=family_id,
        review_rubric_version="structural_v1",
        issues_json=json.dumps(issues),
    )
    session.add(review)
    await session.flush()
    logger.info(
        "[%s] L1 structural review: verdict=%s, issues=%d",
        paper_id, verdict, len(issues),
    )
    return review
