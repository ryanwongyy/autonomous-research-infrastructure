"""Packager role: assembles final paper package with all artifacts.

Boundary: Computes final hashes and creates an immutable package record.
           Cannot modify content -- only aggregates and hashes.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.acknowledgment_record import AcknowledgmentRecord
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_package import PaperPackage
from app.services.provenance.hasher import (
    compute_merkle_root,
    hash_content,
)
from app.utils import utcnow_naive

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def build_package(
    session: AsyncSession,
    paper_id: str,
    manuscript_latex: str | None = None,
    code_content: str | None = None,
    result_manifest: dict[str, Any] | None = None,
    source_manifest: dict[str, Any] | None = None,
    verification_report: dict[str, Any] | None = None,
) -> PaperPackage:
    """Build the complete paper package.

    1. Collect all artifacts: lock, manuscript, code, data, results, reviews
    2. Compute individual hashes for each component
    3. Compute Merkle root of all component hashes
    4. Generate authorship declaration template (human-only)
    5. Generate AI contribution log (what Claude did at each stage)
    6. Generate standardized disclosure text
    7. Create PaperPackage record
    8. Update Paper.funnel_stage to 'candidate'
    """
    paper = await _load_paper(session, paper_id)

    # Load lock artifact
    lock = await _load_active_lock(session, paper_id)

    # -----------------------------------------------------------------------
    # 1-2. Collect artifacts and compute individual hashes
    # -----------------------------------------------------------------------
    component_hashes: dict[str, str] = {}

    # Lock artifact hash
    lock_hash: str | None = None
    if lock:
        lock_hash = lock.lock_hash
        component_hashes["lock_artifact"] = lock_hash

    # Source manifest hash
    source_hash: str | None = None
    if source_manifest:
        source_bytes = json.dumps(source_manifest, sort_keys=True).encode("utf-8")
        source_hash = hash_content(source_bytes)
        component_hashes["source_manifest"] = source_hash

    # Analysis code hash
    code_hash: str | None = None
    if code_content:
        code_hash = hash_content(code_content.encode("utf-8"))
        component_hashes["analysis_code"] = code_hash

    # Result hash
    result_hash: str | None = None
    if result_manifest:
        result_bytes = json.dumps(result_manifest, sort_keys=True).encode("utf-8")
        result_hash = hash_content(result_bytes)
        component_hashes["results"] = result_hash

    # Manuscript hash
    manuscript_hash: str | None = None
    if manuscript_latex:
        manuscript_hash = hash_content(manuscript_latex.encode("utf-8"))
        component_hashes["manuscript"] = manuscript_hash

    # Verification report hash
    if verification_report:
        verify_bytes = json.dumps(verification_report, sort_keys=True).encode("utf-8")
        component_hashes["verification"] = hash_content(verify_bytes)

    # -----------------------------------------------------------------------
    # 3. Compute Merkle root
    # -----------------------------------------------------------------------
    hash_values = sorted(component_hashes.values())  # Sort for determinism
    merkle_root = compute_merkle_root(hash_values) if hash_values else hash_content(b"")

    # -----------------------------------------------------------------------
    # 4. Authorship declaration template
    # -----------------------------------------------------------------------
    authorship_declaration = json.dumps(
        {
            "declaration_type": "human_authorship_required",
            "template": {
                "human_authors": [
                    {
                        "name": "[REQUIRED: Full name]",
                        "affiliation": "[REQUIRED: Institution]",
                        "contribution": "[REQUIRED: Specific contributions]",
                        "corresponding": False,
                    }
                ],
                "certification": (
                    "I/We certify that all human authors listed above made "
                    "substantive intellectual contributions to this work beyond "
                    "supervising AI-generated output."
                ),
                "signed_date": None,
            },
            "note": "This paper was generated with AI assistance. Human authorship "
            "must be established before submission to any venue.",
        },
        indent=2,
    )

    # -----------------------------------------------------------------------
    # 5. AI contribution log
    # -----------------------------------------------------------------------
    ai_contribution_log = json.dumps(
        {
            "pipeline_version": "phase_3_bounded_roles",
            "model": settings.claude_opus_model,
            "stages": {
                "scout": {
                    "role": "Idea generation and screening",
                    "ai_contribution": "Generated research idea cards from governance landscape gaps; "
                    "screened ideas on 6 dimensions",
                    "human_oversight": "Human approves or rejects ideas before proceeding",
                },
                "designer": {
                    "role": "Research design creation",
                    "ai_contribution": "Generated research design YAML with all required fields; "
                    "produced narrative memo explaining design choices",
                    "human_oversight": "Human reviews and locks the design",
                },
                "data_steward": {
                    "role": "Source manifest and data fetching",
                    "ai_contribution": "Matched research needs to available source cards; "
                    "built source manifest with fetch parameters",
                    "human_oversight": "Human verifies source selections and data quality",
                },
                "analyst": {
                    "role": "Analysis code generation and execution",
                    "ai_contribution": "Generated analysis code implementing locked design; "
                    "executed code to produce result objects",
                    "human_oversight": "Human reviews code and validates results",
                },
                "drafter": {
                    "role": "Manuscript composition",
                    "ai_contribution": "Composed full LaTeX manuscript with evidence-linked claims; "
                    "generated bibliography entries",
                    "human_oversight": "Human reviews manuscript for accuracy and quality",
                },
                "verifier": {
                    "role": "Claim verification",
                    "ai_contribution": "Cross-checked all claims against evidence base; "
                    "flagged causal language violations and tier compliance issues",
                    "human_oversight": "Human reviews verification report",
                },
                "packager": {
                    "role": "Package assembly",
                    "ai_contribution": "Computed artifact hashes and Merkle root; "
                    "generated disclosure and contribution log",
                    "human_oversight": "Human signs authorship declaration before submission",
                },
            },
            "component_hashes": component_hashes,
            "merkle_root": merkle_root,
            "packaged_at": datetime.now(UTC).isoformat(),
        },
        indent=2,
    )

    # -----------------------------------------------------------------------
    # 6. Standardized disclosure text
    # -----------------------------------------------------------------------
    disclosure_text = (
        "DISCLOSURE OF AI ASSISTANCE\n"
        "\n"
        "This paper was produced with the assistance of an AI-powered research "
        "pipeline (ProjectAPE, using Anthropic Claude). The AI system contributed "
        "to the following stages:\n"
        "\n"
        "- Research idea generation and screening\n"
        "- Research design specification\n"
        "- Data source identification and manifest construction\n"
        "- Analysis code generation\n"
        "- Manuscript drafting with evidence-linked claims\n"
        "- Automated claim verification against source evidence\n"
        "\n"
        "All AI-generated content was subject to human review. The research design "
        "was frozen via a cryptographic lock artifact before downstream processing. "
        "Every empirical claim in the manuscript maps to a verified source span or "
        "analysis result object.\n"
        "\n"
        f"Package integrity hash (Merkle root): {merkle_root}\n"
        f"Lock artifact hash: {lock_hash or 'N/A'}\n"
        "\n"
        "Human authors are solely responsible for the intellectual content and any "
        "errors in this work. The AI contribution log and verification report are "
        "available as supplementary materials."
    )

    # Collegial review acknowledgments
    ack_result = await session.execute(
        select(AcknowledgmentRecord).where(AcknowledgmentRecord.paper_id == paper_id)
    )
    ack_records = ack_result.scalars().all()
    if ack_records:
        ack_lines = [a.acknowledgment_text for a in ack_records if a.acknowledgment_text]
        if ack_lines:
            disclosure_text += "\n\nACKNOWLEDGMENTS\n\n" + " ".join(ack_lines)

    # -----------------------------------------------------------------------
    # 7. Create PaperPackage record
    # -----------------------------------------------------------------------
    package_path = os.path.join(settings.papers_dir, paper_id, "package_v1")

    # Check for existing package and increment version if needed
    existing_stmt = select(PaperPackage).where(PaperPackage.paper_id == paper_id)
    existing_result = await session.execute(existing_stmt)
    existing_package = existing_result.scalar_one_or_none()

    version_major = 1
    version_minor = 0
    if existing_package:
        version_major = existing_package.version_major
        version_minor = existing_package.version_minor + 1
        package_path = os.path.join(
            settings.papers_dir,
            paper_id,
            f"package_v{version_major}.{version_minor}",
        )
        # Remove old package record (unique constraint on paper_id)
        await session.delete(existing_package)
        await session.flush()

    package = PaperPackage(
        paper_id=paper_id,
        manifest_hash=merkle_root,
        package_path=package_path,
        lock_artifact_hash=lock_hash,
        source_manifest_hash=source_hash,
        code_hash=code_hash,
        result_hash=result_hash,
        manuscript_hash=manuscript_hash,
        version_major=version_major,
        version_minor=version_minor,
        authorship_declaration=authorship_declaration,
        ai_contribution_log=ai_contribution_log,
        disclosure_text=disclosure_text,
        # paper_packages.created_at is TIMESTAMP WITHOUT TIME ZONE
        # on Postgres (run #25140027480 hit DataError on this write).
        created_at=utcnow_naive(),
    )
    session.add(package)

    # -----------------------------------------------------------------------
    # 8. Persist artifacts to disk + update Paper.{paper_tex_path,
    #    code_path, data_path} so L1 structural review can find them.
    #
    # Production run #25163518619 reached Packager but L1 then reported
    # CRITICAL "Required artifact missing: manuscript" because the Paper
    # row had `paper_tex_path = None` — content was hashed and stored on
    # PaperPackage but never written to disk. L1 reads `paper.paper_tex_path`
    # / `paper.code_path` / `paper.data_path` (see l1_structural.py:94-96)
    # so each must point at a real file.
    #
    # Writes are best-effort: a filesystem error here doesn't kill the
    # pipeline (the package record still has the hashes). But on the
    # happy path the files exist and L1 advances past artifact_missing.
    # -----------------------------------------------------------------------
    artifact_paths = _write_package_artifacts(
        package_path=package_path,
        manuscript_latex=manuscript_latex,
        code_content=code_content,
        source_manifest=source_manifest,
        result_manifest=result_manifest,
    )

    # -----------------------------------------------------------------------
    # 9. Update paper funnel stage + artifact path columns
    # -----------------------------------------------------------------------
    paper.funnel_stage = "candidate"
    if artifact_paths.get("manuscript"):
        paper.paper_tex_path = artifact_paths["manuscript"]
    if artifact_paths.get("code"):
        paper.code_path = artifact_paths["code"]
    if artifact_paths.get("data"):
        paper.data_path = artifact_paths["data"]
    session.add(paper)
    await session.flush()

    logger.info(
        "Packager built package for paper %s (merkle=%s, v%d.%d)",
        paper_id,
        merkle_root[:16],
        version_major,
        version_minor,
    )
    return package


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    paper = result.scalar_one_or_none()
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found.")
    return paper


async def _load_active_lock(session: AsyncSession, paper_id: str) -> LockArtifact | None:
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _write_package_artifacts(
    *,
    package_path: str,
    manuscript_latex: str | None,
    code_content: str | None,
    source_manifest: dict[str, Any] | None,
    result_manifest: dict[str, Any] | None,
) -> dict[str, str]:
    """Persist generated artifacts to disk under ``package_path``.

    Writes manuscript.tex / code/analysis.py / data/manifest.json /
    results/results.json so the L1 structural reviewer (and any external
    consumer) can read content from a real filesystem path. Returns a
    mapping of ``{artifact_name: relative_path_to_papers_dir_or_absolute}``
    that the caller stores on the Paper row.

    Best-effort: any IO error logs and continues. The PaperPackage record
    still has hashes for every component, so a missing file is recoverable
    from the DB; the L1 review will just complain on this particular run.
    """
    out: dict[str, str] = {}

    try:
        os.makedirs(package_path, exist_ok=True)
    except OSError as e:
        logger.warning(
            "Packager: failed to create package dir %s: %s — skipping artifact writes",
            package_path,
            e,
        )
        return out

    if manuscript_latex:
        manuscript_file = os.path.join(package_path, "manuscript.tex")
        try:
            with open(manuscript_file, "w", encoding="utf-8") as f:
                f.write(manuscript_latex)
            out["manuscript"] = manuscript_file
        except OSError as e:
            logger.warning(
                "Packager: failed to write manuscript.tex: %s", e
            )

    if code_content:
        code_dir = os.path.join(package_path, "code")
        try:
            os.makedirs(code_dir, exist_ok=True)
            code_file = os.path.join(code_dir, "analysis.py")
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code_content)
            out["code"] = code_file
        except OSError as e:
            logger.warning("Packager: failed to write analysis.py: %s", e)

    if source_manifest is not None:
        data_dir = os.path.join(package_path, "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
            data_file = os.path.join(data_dir, "manifest.json")
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(source_manifest, f, indent=2, sort_keys=True)
            out["data"] = data_file
        except OSError as e:
            logger.warning("Packager: failed to write data manifest: %s", e)

    if result_manifest is not None:
        results_dir = os.path.join(package_path, "results")
        try:
            os.makedirs(results_dir, exist_ok=True)
            results_file = os.path.join(results_dir, "results.json")
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(result_manifest, f, indent=2, sort_keys=True)
            # Not stored on Paper — this is supplementary, not what L1 checks.
            out["results"] = results_file
        except OSError as e:
            logger.warning("Packager: failed to write results.json: %s", e)

    return out
