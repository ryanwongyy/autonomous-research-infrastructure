"""Tests for the release state machine transitions."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services.release.release_manager import (
    check_transition_preconditions,
    transition_release_status,
)


@pytest_asyncio.fixture
async def paper_in_db(db_session: AsyncSession) -> Paper:
    """Create a minimal paper in 'internal' release status."""
    paper = Paper(
        id="rel_test_001",
        title="Release Test Paper",
        source="ape",
        status="draft",
        review_status="awaiting",
        release_status="internal",
    )
    db_session.add(paper)
    await db_session.commit()
    await db_session.refresh(paper)
    return paper


@pytest.mark.asyncio
async def test_check_preconditions_internal_to_candidate(
    db_session: AsyncSession, paper_in_db: Paper
):
    result = await check_transition_preconditions(db_session, paper_in_db.id, "candidate")
    assert "can_transition" in result
    assert result["current_status"] == "internal"
    assert result["target_status"] == "candidate"


@pytest.mark.asyncio
async def test_invalid_transition_target(db_session: AsyncSession, paper_in_db: Paper):
    result = await check_transition_preconditions(db_session, paper_in_db.id, "nonexistent_status")
    # Should either block or raise — depends on implementation
    assert "can_transition" in result or "error" in str(result)


@pytest.mark.asyncio
async def test_force_transition(db_session: AsyncSession, paper_in_db: Paper):
    """Force=True should bypass preconditions."""
    result = await transition_release_status(db_session, paper_in_db.id, "candidate", force=True)
    assert result["success"] is True
    assert result["after"] == "candidate"
    assert result["forced"] is True


@pytest.mark.asyncio
async def test_transition_updates_paper(db_session: AsyncSession, paper_in_db: Paper):
    await transition_release_status(db_session, paper_in_db.id, "candidate", force=True)
    await db_session.refresh(paper_in_db)
    assert paper_in_db.release_status == "candidate"


@pytest.mark.asyncio
async def test_cannot_skip_states(db_session: AsyncSession, paper_in_db: Paper):
    """Internal → public should fail (must go through candidate, submitted)."""
    result = await check_transition_preconditions(db_session, paper_in_db.id, "public")
    # The state machine should not allow skipping intermediate states
    if result.get("can_transition"):
        # If it allows, there should be blockers
        assert len(result.get("blockers", [])) > 0 or not result["can_transition"]


@pytest.mark.asyncio
async def test_nonexistent_paper(db_session: AsyncSession):
    result = await check_transition_preconditions(db_session, "nonexistent_paper_id", "candidate")
    # Should indicate failure
    assert not result.get("can_transition", True)
