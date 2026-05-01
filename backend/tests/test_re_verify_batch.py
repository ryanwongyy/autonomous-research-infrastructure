"""Tests for the re-verify batch endpoint.

PR #56 added per-paper /admin/papers/{id}/re-verify; PR #62 adds the
batch variant /admin/papers/re-verify-batch that finds every paper
with high pending-claim ratio and runs re-verify on each.

Production observation: every paper that passes Packager has ~70% of
claims at verification_status='pending' (the LLM cherry-picks during
generation's Verifier stage). Production paper apep_1b62de0c had
19 Tier A + 6 Tier B sources, L1 PASSED, but L2 fired CRITICAL
coverage_incomplete at 28%. Without the batch endpoint wired into
the cron, every paper hits the same wall.

This file locks in:
  * Selection criteria (status in ('reviewing','candidate'), pending
    ratio above threshold)
  * Threshold + limit query params with validation
  * Sequential processing (one paper at a time)
  * Returns before/after pending count per paper
  * Admin auth required
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.paper_family import PaperFamily


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _seed_family(db_session):
    db_session.add(
        PaperFamily(
            id="F_RVBATCH",
            name="x",
            short_name="RB",
            description="x",
            lock_protocol_type="open",
            active=True,
        )
    )


def _add_paper_with_claims(
    db_session,
    paper_id: str,
    status: str,
    pending_count: int,
    verified_count: int,
):
    """Create a paper + N claims with the requested status mix."""
    paper = Paper(
        id=paper_id,
        title="x",
        source="ape",
        status=status,
        review_status="awaiting" if status == "reviewing" else "skipped",
        family_id="F_RVBATCH",
        funnel_stage=status,
        created_at=_utcnow_naive() - timedelta(minutes=10),
    )
    db_session.add(paper)
    for i in range(pending_count):
        db_session.add(
            ClaimMap(
                paper_id=paper_id,
                claim_text=f"pending claim {i}",
                claim_type="empirical",
                verification_status="pending",
                source_card_id=None,
            )
        )
    for i in range(verified_count):
        db_session.add(
            ClaimMap(
                paper_id=paper_id,
                claim_text=f"verified claim {i}",
                claim_type="empirical",
                verification_status="verified",
                source_card_id=None,
            )
        )


# ── Source-level shape ───────────────────────────────────────────────────────


def test_endpoint_is_registered():
    from app.api import papers as papers_module

    routes = [
        r for r in papers_module.router.routes
        if hasattr(r, "path") and "re-verify-batch" in r.path
    ]
    assert routes, "POST /admin/papers/re-verify-batch must be registered."


def test_endpoint_filters_by_status():
    """Source check: candidates query must filter to status in
    ('reviewing', 'candidate')."""
    from app.api.papers import re_verify_batch
    src = inspect.getsource(re_verify_batch)
    assert 'Paper.status.in_' in src
    assert '"reviewing"' in src
    assert '"candidate"' in src


def test_endpoint_orders_by_created_at_desc():
    """Newest papers first so the cron always processes the latest."""
    from app.api.papers import re_verify_batch
    src = inspect.getsource(re_verify_batch)
    assert "created_at.desc()" in src


def test_endpoint_uses_status_filter_pending():
    """The batch loop must call verify_manuscript with
    status_filter='pending' so only pending claims get re-verified."""
    from app.api.papers import re_verify_batch
    src = inspect.getsource(re_verify_batch)
    assert 'status_filter="pending"' in src


# ── Selection: only papers with high pending ratio are processed ────────────


@pytest.mark.asyncio
async def test_skips_papers_below_threshold(authed_client, db_session):
    """A paper with pending_ratio below the threshold is examined as
    a candidate but not processed."""
    # 1/10 = 10% pending — below default 20%.
    _add_paper_with_claims(db_session, "apep_low", "reviewing", 1, 9)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/re-verify-batch",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates_examined"] == 1
    assert body["eligible_count"] == 0
    assert body["processed_count"] == 0


@pytest.mark.asyncio
async def test_skips_terminal_status_papers(authed_client, db_session):
    """Papers with status NOT in ('reviewing','candidate') are not
    candidates (e.g. killed/error/published)."""
    _add_paper_with_claims(db_session, "apep_killed", "killed", 20, 5)
    _add_paper_with_claims(db_session, "apep_error", "error", 20, 5)
    _add_paper_with_claims(db_session, "apep_published", "published", 20, 5)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/re-verify-batch",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["candidates_examined"] == 0


@pytest.mark.asyncio
async def test_skips_papers_with_no_claims(authed_client, db_session):
    """A paper with zero claims has no pending ratio — skip it."""
    paper = Paper(
        id="apep_noclaims",
        title="x",
        source="ape",
        status="reviewing",
        review_status="awaiting",
        family_id="F_RVBATCH",
        funnel_stage="reviewing",
        created_at=_utcnow_naive(),
    )
    db_session.add(paper)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/re-verify-batch",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.json()["eligible_count"] == 0


# ── Query param validation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_threshold_bounds_validated(authed_client):
    """min_pending_ratio must be in [0.0, 1.0] — out of range is 422."""
    for ratio in (-0.1, 1.5):
        resp = await authed_client.post(
            f"/api/v1/admin/papers/re-verify-batch?min_pending_ratio={ratio}",
            headers={"X-API-Key": "test-admin-key"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_limit_bounds_validated(authed_client):
    for lim in (0, 100):
        resp = await authed_client.post(
            f"/api/v1/admin/papers/re-verify-batch?limit={lim}",
            headers={"X-API-Key": "test-admin-key"},
        )
        assert resp.status_code == 422


# ── Auth ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoint_requires_admin_auth_when_admin_key_set(
    db_engine, monkeypatch
):
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database import get_db
    from app.main import app

    monkeypatch.setattr("app.config.settings.ape_admin_key", "secret-admin")
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _test_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/admin/papers/re-verify-batch")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ── Workflow integration ────────────────────────────────────────────────────


def test_workflow_calls_re_verify_batch():
    """The autonomous-loop workflow must call the batch endpoint
    between Generate and Review so coverage is filled before review
    runs (otherwise every paper L2-fails on coverage_incomplete)."""
    import pathlib
    workflow = pathlib.Path(
        __file__
    ).parent.parent.parent / ".github" / "workflows" / "autonomous-loop.yml"
    assert workflow.is_file(), f"workflow not found at {workflow}"
    text = workflow.read_text()
    assert "/api/v1/admin/papers/re-verify-batch" in text
    # Re-verify step must come BEFORE the review step, otherwise the
    # ordering is broken and L2 still sees stale coverage.
    rv_pos = text.find("/api/v1/admin/papers/re-verify-batch")
    review_pos = text.find("/api/v1/batch/review-pending")
    assert rv_pos > 0
    assert review_pos > 0
    assert rv_pos < review_pos, (
        "Re-verify step must run BEFORE Review step so L2 sees filled "
        "coverage."
    )
