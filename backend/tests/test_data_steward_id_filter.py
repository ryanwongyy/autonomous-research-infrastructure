"""Regression tests for the Data Steward stage's source-ID filtering.

Background: production run #25130390167 had both papers reach the Data
Steward stage successfully but die because the LLM hallucinated source
IDs like ``UNREGISTERED::fpds_ng_bulk`` and ``NONE_REGISTERED`` that
aren't in the source-card registry. Every fetch raised
"Source card not found", ``snapshots_created`` was 0, and the stage
returned ``failed`` with no useful diagnostic.

These tests lock in the fix:
  - Hallucinated source IDs are filtered out before the fetch loop.
  - Falls back to broad-purpose registered defaults if zero valid IDs
    remain after filtering.
  - The ``failed`` return now carries a ``reason`` field instead of
    being silently empty.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.source_card import SourceCard
from app.services.paper_generation.orchestrator import _stage_data_steward


async def _seed_paper(session: AsyncSession, paper_id: str = "apep_ds01") -> Paper:
    paper = Paper(
        id=paper_id,
        title="DS test",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F1",
        funnel_stage="locked",
    )
    session.add(paper)
    await session.flush()
    return paper


async def _seed_source_card(session: AsyncSession, sc_id: str) -> None:
    sc = SourceCard(
        id=sc_id,
        name=sc_id.replace("_", " ").title(),
        tier="A",
        source_type="api",
        access_method="http",
        # claim_permissions/claim_prohibitions are NOT NULL on the model.
        claim_permissions="[]",
        claim_prohibitions="[]",
        active=True,
    )
    session.add(sc)
    await session.flush()


@pytest.mark.asyncio
async def test_filters_unregistered_source_ids(db_session: AsyncSession):
    """Hallucinated ``UNREGISTERED::*`` IDs are dropped before fetching.

    The single registered source ('federal_register') is still fetched.
    """
    paper = await _seed_paper(db_session)
    await _seed_source_card(db_session, "federal_register")

    manifest = {
        "sources": [
            {"source_card_id": "UNREGISTERED::fpds_ng_bulk", "fetch_params": {}},
            {"source_card_id": "federal_register", "fetch_params": {}},
            {"source_card_id": "NONE_REGISTERED", "fetch_params": {}},
        ]
    }
    fetch_mock = AsyncMock()

    with (
        patch(
            "app.services.paper_generation.orchestrator.build_source_manifest",
            new=AsyncMock(return_value=manifest),
        ),
        patch(
            "app.services.paper_generation.orchestrator.fetch_and_snapshot",
            new=fetch_mock,
        ),
    ):
        result = await _stage_data_steward(db_session, paper, provider=None)

    # Only the registered ID should have been fetched
    assert fetch_mock.call_count == 1
    called_with_ids = {c.kwargs["source_id"] for c in fetch_mock.call_args_list}
    assert called_with_ids == {"federal_register"}

    assert result["status"] == "completed"
    assert result["snapshots_created"] == 1
    assert "UNREGISTERED::fpds_ng_bulk" in result["dropped_source_ids"]
    assert "NONE_REGISTERED" in result["dropped_source_ids"]


@pytest.mark.asyncio
async def test_falls_back_when_all_ids_invalid(db_session: AsyncSession):
    """When 0 valid IDs remain, fall back to default whitelist if available."""
    paper = await _seed_paper(db_session)
    await _seed_source_card(db_session, "federal_register")
    await _seed_source_card(db_session, "regulations_gov")

    manifest = {
        "sources": [
            {"source_card_id": "NONE_REGISTERED", "fetch_params": {}},
            {"source_card_id": "UNREGISTERED::foo", "fetch_params": {}},
        ]
    }
    fetch_mock = AsyncMock()

    with (
        patch(
            "app.services.paper_generation.orchestrator.build_source_manifest",
            new=AsyncMock(return_value=manifest),
        ),
        patch(
            "app.services.paper_generation.orchestrator.fetch_and_snapshot",
            new=fetch_mock,
        ),
    ):
        result = await _stage_data_steward(db_session, paper, provider=None)

    # Fallback used both broad-purpose defaults
    called_ids = {c.kwargs["source_id"] for c in fetch_mock.call_args_list}
    assert called_ids == {"federal_register", "regulations_gov"}
    assert result["status"] == "completed"
    assert result["snapshots_created"] == 2


@pytest.mark.asyncio
async def test_failed_status_carries_reason(db_session: AsyncSession):
    """A failed stage must surface a non-empty ``reason``.

    Otherwise ``error_message`` falls through to "(no error message)" in
    the API response and the operator can't tell what went wrong.
    """
    paper = await _seed_paper(db_session)
    await _seed_source_card(db_session, "federal_register")

    manifest = {"sources": [{"source_card_id": "federal_register", "fetch_params": {}}]}
    # fetch_and_snapshot always raises — simulates real-world fetch error
    fetch_mock = AsyncMock(side_effect=RuntimeError("API rate limited"))

    with (
        patch(
            "app.services.paper_generation.orchestrator.build_source_manifest",
            new=AsyncMock(return_value=manifest),
        ),
        patch(
            "app.services.paper_generation.orchestrator.fetch_and_snapshot",
            new=fetch_mock,
        ),
    ):
        result = await _stage_data_steward(db_session, paper, provider=None)

    assert result["status"] == "failed"
    assert "reason" in result
    assert result["reason"]  # non-empty
    assert "API rate limited" in result["reason"]
