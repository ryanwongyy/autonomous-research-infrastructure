"""Tests that L1 structural review treats ``source_span_ref`` as a
valid claim link.

Production paper apep_144722c2: 21/25 claims had ``source_span_ref``
populated by PR #36's soft-fallback path (LLM named a source like a
CFR section that wasn't pre-registered as a SourceCard). L1's
``central_claim_unlinked`` check ignored ``source_span_ref`` and
fired CRITICAL on 15 doctrinal claims, blocking review.

This file locks in:

  * A claim with only ``source_span_ref`` populated counts as linked.
  * A claim with only ``source_card_id`` (FK) counts as linked.
  * A claim with only ``result_object_ref`` counts as linked.
  * A claim with all three None counts as unlinked.
  * Soft-linked-only claims log a quality-signal INFO message.
"""

from __future__ import annotations

import json
import logging

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.review import Review
from app.services.review_pipeline.l1_structural import run_structural_review


@pytest_asyncio.fixture
async def seeded_paper(db_session):
    """Create a Paper with on-disk artifact paths so L1's section-2
    artifact_checks pass — leaving section-3 (claim links) as the only
    failure surface this file exercises."""
    family = PaperFamily(
        id="F_L1_TEST",
        name="L1 link-check test family",
        short_name="L1T",
        description="for soft-link recognition tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)

    paper = Paper(
        id="apep_l1soft",
        title="Test paper",
        source="ape",
        status="candidate",
        review_status="awaiting",
        family_id="F_L1_TEST",
        funnel_stage="candidate",
        # Stub artifact paths so L1 doesn't hit artifact_missing first.
        # Files don't have to exist for this test — L1's check is on
        # whether the field is populated, not on content read.
        paper_tex_path="/tmp/fake_manuscript.tex",
        code_path="/tmp/fake_code.py",
        data_path="/tmp/fake_data.json",
    )
    db_session.add(paper)
    await db_session.commit()
    return paper


def _add_claim(
    session, paper_id, *, claim_type, source_card_id=None,
    result_object_ref=None, source_span_ref=None,
):
    """Add a ClaimMap row. ``result_object_ref`` and ``source_span_ref``
    are stored as JSON strings (TEXT columns); accept dict for ergonomics
    and serialise here."""
    if isinstance(result_object_ref, dict):
        result_object_ref = json.dumps(result_object_ref)
    if isinstance(source_span_ref, dict):
        source_span_ref = json.dumps(source_span_ref)
    cm = ClaimMap(
        paper_id=paper_id,
        claim_text=f"test claim ({claim_type})",
        claim_type=claim_type,
        source_card_id=source_card_id,
        result_object_ref=result_object_ref,
        source_span_ref=source_span_ref,
        verification_status="pending",
    )
    session.add(cm)
    return cm


async def _l1_issues(session, paper_id):
    await run_structural_review(session, paper_id)
    review = (
        await session.execute(
            select(Review)
            .where(Review.paper_id == paper_id, Review.stage == "l1_structural")
            .order_by(Review.id.desc())
        )
    ).scalar_one()
    return review.content, review.verdict


# ── Single-pointer cases ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_linked_via_source_card_id_only(seeded_paper, db_session):
    """A claim with only ``source_card_id`` set counts as linked.

    L1's check is "is the field non-None?", so we don't need an actual
    SourceCard row in the test DB — just a non-None value. (The full
    FK enforcement is exercised at insert time in production via
    Postgres; SQLite doesn't enforce by default.)
    """
    from app.models.source_card import SourceCard

    db_session.add(
        SourceCard(
            id="SC_TEST_FK",
            name="Test source for FK",
            tier=2,
            source_type="document",
            access_method="manual",
            claim_permissions="[]",
            claim_prohibitions="[]",
            required_corroboration="[]",
            active=True,
        )
    )
    await db_session.flush()

    _add_claim(
        db_session, seeded_paper.id, claim_type="empirical",
        source_card_id="SC_TEST_FK",
    )
    await db_session.commit()
    content, _ = await _l1_issues(db_session, seeded_paper.id)
    assert "central_claim_unlinked" not in content
    assert "claim_map_unlinked" not in content


@pytest.mark.asyncio
async def test_claim_linked_via_source_span_ref_only(seeded_paper, db_session):
    """A claim with ONLY source_span_ref populated counts as linked.

    This is the production failure mode this PR fixes — PR #36's soft
    fallback stores LLM-named sources here when they're not in the
    SourceCard registry. The previous L1 check ignored this field and
    flagged 15 such claims as CRITICAL on apep_144722c2.
    """
    _add_claim(
        db_session,
        seeded_paper.id,
        claim_type="doctrinal",
        source_span_ref={"name": "29 CFR § 1607.4(d)", "registered": False},
    )
    _add_claim(
        db_session,
        seeded_paper.id,
        claim_type="empirical",
        source_span_ref={"name": "Griggs v. Duke Power, 401 U.S. 424"},
    )
    await db_session.commit()

    content, _verdict = await _l1_issues(db_session, seeded_paper.id)
    assert "central_claim_unlinked" not in content
    assert "claim_map_unlinked" not in content
    # No CRITICAL claim issues = L1 should pass on this dimension.


@pytest.mark.asyncio
async def test_claim_linked_via_result_object_ref_only(seeded_paper, db_session):
    _add_claim(
        db_session, seeded_paper.id, claim_type="empirical",
        result_object_ref={"name": "regression_table_1"},
    )
    await db_session.commit()
    content, _ = await _l1_issues(db_session, seeded_paper.id)
    assert "central_claim_unlinked" not in content
    assert "claim_map_unlinked" not in content


# ── Truly-unlinked cases still flag ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_with_no_pointers_is_flagged(seeded_paper, db_session):
    _add_claim(
        db_session, seeded_paper.id, claim_type="empirical",
        # all three pointer fields default None
    )
    await db_session.commit()
    content, _verdict = await _l1_issues(db_session, seeded_paper.id)
    # Empirical → also central → both messages fire.
    assert "claim_map_unlinked" in content
    assert "central_claim_unlinked" in content


@pytest.mark.asyncio
async def test_descriptive_claim_with_no_pointers_only_warns(
    seeded_paper, db_session
):
    """A non-central (descriptive) claim with no pointers fires only
    the WARNING claim_map_unlinked, not the CRITICAL central_*."""
    _add_claim(
        db_session, seeded_paper.id, claim_type="descriptive",
    )
    await db_session.commit()
    content, _ = await _l1_issues(db_session, seeded_paper.id)
    assert "claim_map_unlinked" in content
    assert "central_claim_unlinked" not in content


# ── Quality-signal log line ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_soft_linked_claims_emit_info_log(
    seeded_paper, db_session, caplog
):
    """When a paper has soft-linked claims, L1 logs an INFO message
    with the count. Operators reading logs can spot Drafter naming
    sources outside the SourceCard registry without it being treated
    as a structural failure."""
    _add_claim(
        db_session, seeded_paper.id, claim_type="doctrinal",
        source_span_ref={"name": "Some unregistered source"},
    )
    _add_claim(
        db_session, seeded_paper.id, claim_type="empirical",
        source_span_ref={"name": "Another"},
    )
    _add_claim(
        db_session, seeded_paper.id, claim_type="empirical",
        result_object_ref={"name": "result_x"},  # NOT soft-linked
    )
    await db_session.commit()

    with caplog.at_level(logging.INFO, logger="app.services.review_pipeline.l1_structural"):
        await run_structural_review(db_session, seeded_paper.id)

    soft_logs = [
        r for r in caplog.records
        if "soft-linked" in r.getMessage()
    ]
    assert soft_logs, "Expected an INFO log mentioning soft-linked claims"
    msg = soft_logs[0].getMessage()
    # Pattern: "...has 2/3 soft-linked claims..."
    assert "2/3" in msg, f"Expected '2/3' in log message, got: {msg}"


# ── Mixed realistic case (mirrors production paper apep_144722c2) ────────────


@pytest.mark.asyncio
async def test_apep_144722c2_shape_does_not_fail_critical(
    seeded_paper, db_session
):
    """Mirror the production paper's claim breakdown:
      * 4 result-linked (analyst output)
      * 21 soft-linked (LLM-named legal authorities)
      * 0 hard-linked
      * 0 truly empty

    With the new L1 check, none of these trigger central_claim_unlinked
    CRITICAL. The previous check fired CRITICAL on 15/25 of them.
    """
    # 4 result-linked (a mix of empirical + descriptive)
    for i in range(4):
        _add_claim(
            db_session, seeded_paper.id,
            claim_type="empirical" if i < 2 else "descriptive",
            result_object_ref={"name": f"result_{i}"},
        )
    # 21 soft-linked: 15 doctrinal central + 6 descriptive
    for i in range(15):
        _add_claim(
            db_session, seeded_paper.id, claim_type="doctrinal",
            source_span_ref={"name": f"29 CFR § 1607.{i}"},
        )
    for i in range(6):
        _add_claim(
            db_session, seeded_paper.id, claim_type="descriptive",
            source_span_ref={"name": f"general literature {i}"},
        )
    await db_session.commit()

    content, _verdict = await _l1_issues(db_session, seeded_paper.id)
    assert "central_claim_unlinked" not in content, (
        "CRITICAL central_claim_unlinked must NOT fire when claims are "
        "soft-linked via source_span_ref. PR #36 added that field "
        "specifically as a fallback; L1 must respect it."
    )
    assert "claim_map_unlinked" not in content, (
        "WARNING claim_map_unlinked must NOT fire either — every claim "
        "has at least one of the three link pointers."
    )
