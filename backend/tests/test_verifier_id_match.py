"""Tests that the Verifier matches LLM output to ClaimMap rows by
integer ``claim_id`` (with text fallback).

Production paper apep_6fc2020e had 25 claims but only 5 got their
verification_status updated. The bug: the writeback path used
``verify_map.get(claim.claim_text)`` — exact-string matching against
the LLM's echoed claim_text. The LLM paraphrased or summarised 20 of
the 25 texts, so 20 lookups returned None and those claims stayed
``pending``. Result: a paper with 24/25 claims sourced + 96% coverage
ended up with verification_status {verified=0, failed=5, pending=20}.

This file locks in:

  * Verifier prompt requests ``claim_id`` from the LLM.
  * Verifier sends ``claim_id`` in claims_data so the LLM has it.
  * ``_update_claim_statuses`` matches by id first, falls back to text.
  * Mismatched claim_text but matching claim_id still updates status.
  * Genuinely missing claims (no id, no matching text) stay pending
    and get logged at WARNING.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.paper_generation.roles import verifier as verifier_mod
from app.services.paper_generation.roles.verifier import (
    VERIFY_USER_PROMPT,
    _update_claim_statuses,
    verify_manuscript,
)

# ── Source-inspection: prompt + claims_data include claim_id ─────────────────


def test_prompt_template_requests_claim_id():
    """The schema in the prompt must include ``claim_id`` so the LLM
    knows it should be echoed back."""
    assert "claim_id" in VERIFY_USER_PROMPT, (
        "VERIFY_USER_PROMPT must request claim_id in the response schema."
    )


def test_verify_manuscript_sends_claim_id_in_claims_data():
    """Source inspection: verify_manuscript builds claims_data with
    ``"claim_id": c.id``. Without the id in the input, the LLM has
    nothing to echo back."""
    src = inspect.getsource(verify_manuscript)
    assert '"claim_id": c.id' in src, (
        "verify_manuscript must include claim_id when building claims_data."
    )


# ── Behavioural: writeback matches by id when text doesn't ───────────────────


@pytest_asyncio.fixture
async def seeded_paper(db_session):
    family = PaperFamily(
        id="F_VERIFIER_TEST",
        name="Verifier ID-match test",
        short_name="VIDM",
        description="for ID-matching tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="apep_vidm",
        title="t",
        source="ape",
        status="reviewing",
        review_status="awaiting",
        family_id="F_VERIFIER_TEST",
        funnel_stage="reviewing",
    )
    db_session.add(paper)
    await db_session.commit()
    return paper


async def _add_and_get_claim(session, paper_id, text, claim_type="empirical"):
    cm = ClaimMap(
        paper_id=paper_id,
        claim_text=text,
        claim_type=claim_type,
        verification_status="pending",
    )
    session.add(cm)
    await session.flush()
    return cm


@pytest.mark.asyncio
async def test_id_match_when_text_does_not_match(seeded_paper, db_session):
    """LLM returns claim_id correctly but a paraphrased claim_text.
    The writeback should use the id and update status."""
    c = await _add_and_get_claim(
        db_session, seeded_paper.id, "Original verbatim text"
    )
    verifications: list[dict[str, Any]] = [
        {
            "claim_id": c.id,
            "claim_text": "PARAPHRASED — this isn't the original text",
            "overall": "pass",
        }
    ]
    await _update_claim_statuses(
        db_session, seeded_paper.id, [c], verifications
    )
    await db_session.commit()
    refreshed = (
        await db_session.execute(
            select(ClaimMap).where(ClaimMap.id == c.id)
        )
    ).scalar_one()
    assert refreshed.verification_status == "verified", (
        "ID match should resolve claim regardless of text mismatch."
    )


@pytest.mark.asyncio
async def test_text_fallback_when_id_missing(seeded_paper, db_session):
    """LLM omits claim_id (older response shape) but echoes claim_text
    exactly. Text fallback should still match."""
    c = await _add_and_get_claim(
        db_session, seeded_paper.id, "Exact text echo"
    )
    verifications = [{
        "claim_text": "Exact text echo",
        "overall": "fail",
    }]  # no claim_id
    await _update_claim_statuses(
        db_session, seeded_paper.id, [c], verifications
    )
    await db_session.commit()
    refreshed = (
        await db_session.execute(
            select(ClaimMap).where(ClaimMap.id == c.id)
        )
    ).scalar_one()
    assert refreshed.verification_status == "failed"


@pytest.mark.asyncio
async def test_unmatched_claim_stays_pending(seeded_paper, db_session, caplog):
    """LLM response doesn't include this claim by id or text. Status
    stays pending and a WARNING is logged."""
    c = await _add_and_get_claim(
        db_session, seeded_paper.id, "Original text"
    )
    verifications = [
        {
            "claim_id": 99999,  # different id
            "claim_text": "Some other claim entirely",
            "overall": "pass",
        }
    ]
    with caplog.at_level(
        logging.WARNING,
        logger="app.services.paper_generation.roles.verifier",
    ):
        await _update_claim_statuses(
            db_session, seeded_paper.id, [c], verifications
        )
    await db_session.commit()

    refreshed = (
        await db_session.execute(
            select(ClaimMap).where(ClaimMap.id == c.id)
        )
    ).scalar_one()
    assert refreshed.verification_status == "pending"

    warnings = [
        r for r in caplog.records
        if "unmatched claim" in r.getMessage()
    ]
    assert warnings, "Expected a WARNING log mentioning unmatched claim(s)"


@pytest.mark.asyncio
async def test_apep_6fc2020e_shape_now_resolves_all_claims(
    seeded_paper, db_session
):
    """Mirror production paper's shape: 25 claims, LLM returns ID for
    every one, but paraphrases 20 of the texts.

    With the new code, all 25 should resolve via ID match — replicating
    the full provenance picture rather than the broken 5-of-25 partial
    we saw in production.
    """
    claims: list[ClaimMap] = []
    for i in range(25):
        c = await _add_and_get_claim(
            db_session,
            seeded_paper.id,
            f"original claim {i}",
            claim_type="empirical" if i < 5 else "doctrinal",
        )
        claims.append(c)

    # LLM response: every claim has a claim_id; first 5 echo text exactly,
    # last 20 paraphrase.
    verifications = []
    for i, c in enumerate(claims):
        verifications.append({
            "claim_id": c.id,
            "claim_text": (
                c.claim_text if i < 5
                else f"summary of #{i}: <paraphrased differently>"
            ),
            "overall": "pass" if i < 18 else "fail",
        })

    await _update_claim_statuses(
        db_session, seeded_paper.id, claims, verifications
    )
    await db_session.commit()

    statuses = (
        await db_session.execute(
            select(ClaimMap.verification_status).where(
                ClaimMap.paper_id == seeded_paper.id
            )
        )
    ).scalars().all()

    pending = sum(1 for s in statuses if s == "pending")
    verified = sum(1 for s in statuses if s == "verified")
    failed = sum(1 for s in statuses if s == "failed")

    assert pending == 0, (
        f"Expected 0 pending after Verifier with ID match; got {pending}. "
        f"This is the production failure mode this PR fixes — text-only "
        f"matching left 20/25 claims stuck at pending."
    )
    assert verified == 18
    assert failed == 7


# ── Round-trip dataclass: id round-trips end-to-end ──────────────────────────


def test_writeback_does_not_touch_unmatched_claims(seeded_paper):
    """Sanity: source inspection. The writeback skips claims with no
    matching verification (rather than e.g. defaulting them to 'failed'),
    so a partial response doesn't punish unverified claims."""
    src = inspect.getsource(verifier_mod._update_claim_statuses)
    # The skip path is "if v is None: ... continue" — must be present.
    assert "if v is None:" in src
    assert "continue" in src
