"""Tests for the orphan-paper reaper.

Production paper apep_f237bfc0 (autonomous-loop run 25207115248)
demonstrated the failure mode this reaper closes:
  - Created 07:51:27
  - Last heartbeat from Analyst at 07:54:35 (3 min in)
  - Then 42 minutes of silence — workflow timed out at 45 min
  - status='draft' kill_reason=None paper_tex_path=None forever

The Analyst stage's 900s asyncio.timeout (PR #46) should have fired
and PR #48's status flip should have run. Neither did because the
Render worker process was killed entirely (no Python alive to run
cleanup).

PR #60 closes this from the OUTSIDE: an admin endpoint that scans
for papers with stale heartbeats and non-terminal status, flipping
them to status='killed'.

This file locks in:
  * Reaps papers with stale heartbeats
  * Skips papers with fresh heartbeats
  * Skips papers already in terminal status
  * Reaps papers with no heartbeat at all (worker died before first hb)
  * Sets kill_reason that names the last-seen stage + staleness
  * Configurable threshold via query param
  * Admin auth required
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.paper import Paper
from app.models.paper_family import PaperFamily


def _utcnow_naive() -> datetime:
    """TIMESTAMP WITHOUT TIME ZONE expects naive datetimes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _seed_family(db_session):
    """Every test in this file needs a PaperFamily row."""
    db_session.add(
        PaperFamily(
            id="F_REAP",
            name="Reaper test family",
            short_name="RP",
            description="for orphan reaper tests",
            lock_protocol_type="open",
            active=True,
        )
    )


@pytest.mark.asyncio
async def test_reaps_stale_heartbeat_papers(authed_client, db_session):
    """A paper whose heartbeat is older than the threshold gets
    flipped to status='killed' with a reason."""
    stale_paper = Paper(
        id="apep_stale",
        title="Stale paper",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F_REAP",
        funnel_stage="ingesting",
        created_at=_utcnow_naive() - timedelta(hours=2),
        last_heartbeat_at=_utcnow_naive() - timedelta(hours=1),
        last_heartbeat_stage="analyst",
    )
    db_session.add(stale_paper)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reaped_count"] == 1
    assert body["reaped"][0]["paper_id"] == "apep_stale"
    assert "analyst" in body["reaped"][0]["kill_reason"].lower()

    # DB row updated.
    await db_session.refresh(stale_paper)
    assert stale_paper.status == "killed"
    assert stale_paper.funnel_stage == "killed"
    assert stale_paper.kill_reason is not None
    assert "reaped" in stale_paper.kill_reason.lower()


@pytest.mark.asyncio
async def test_skips_fresh_heartbeat(authed_client, db_session):
    """A paper whose heartbeat is recent must NOT be reaped — it's
    likely still running."""
    fresh_paper = Paper(
        id="apep_fresh",
        title="x",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F_REAP",
        funnel_stage="ingesting",
        created_at=_utcnow_naive() - timedelta(hours=2),
        last_heartbeat_at=_utcnow_naive() - timedelta(minutes=1),
        last_heartbeat_stage="analyst",
    )
    db_session.add(fresh_paper)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["reaped_count"] == 0

    # Status unchanged.
    await db_session.refresh(fresh_paper)
    assert fresh_paper.status == "draft"


@pytest.mark.asyncio
async def test_skips_terminal_status(authed_client, db_session):
    """Papers already at terminal status (candidate, killed, etc.)
    must NOT be reaped even if heartbeats are stale."""
    for st in ("candidate", "killed", "error", "published", "rejected"):
        db_session.add(
            Paper(
                id=f"apep_{st}",
                title="x",
                source="ape",
                status=st,
                review_status="awaiting",
                family_id="F_REAP",
                funnel_stage="reviewing",
                created_at=_utcnow_naive() - timedelta(hours=10),
                last_heartbeat_at=_utcnow_naive() - timedelta(hours=8),
                last_heartbeat_stage="analyst",
            )
        )
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["reaped_count"] == 0


@pytest.mark.asyncio
async def test_reaps_paper_with_no_heartbeat_at_all(authed_client, db_session):
    """If the worker died before writing any heartbeat, the paper has
    last_heartbeat_at=None. Reap it based on created_at age."""
    no_hb_paper = Paper(
        id="apep_nohb",
        title="x",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F_REAP",
        funnel_stage="idea",
        created_at=_utcnow_naive() - timedelta(hours=2),
        # last_heartbeat_at intentionally None
    )
    db_session.add(no_hb_paper)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["reaped_count"] == 1
    assert "no heartbeat" in resp.json()["reaped"][0]["kill_reason"].lower()


@pytest.mark.asyncio
async def test_threshold_is_configurable(authed_client, db_session):
    """A paper that's stale for 20 min isn't reaped at default 30-min
    threshold but IS at threshold=10."""
    paper = Paper(
        id="apep_20min",
        title="x",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F_REAP",
        funnel_stage="ingesting",
        created_at=_utcnow_naive() - timedelta(minutes=22),
        last_heartbeat_at=_utcnow_naive() - timedelta(minutes=20),
        last_heartbeat_stage="analyst",
    )
    db_session.add(paper)
    await db_session.commit()

    # Default threshold (30 min): not reaped.
    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.json()["reaped_count"] == 0

    # Aggressive threshold (10 min): reaped.
    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans?stale_minutes=10",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.json()["reaped_count"] == 1


@pytest.mark.asyncio
async def test_threshold_validation(authed_client):
    """stale_minutes must be 5..240 — degenerate values rejected."""
    # Below floor.
    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans?stale_minutes=2",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 422

    # Above ceiling.
    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans?stale_minutes=600",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kill_reason_includes_stage(authed_client, db_session):
    """The reaper's kill_reason should name the last-seen stage so
    operators can see WHERE the worker was killed."""
    db_session.add(
        Paper(
            id="apep_stage",
            title="x",
            source="ape",
            status="draft",
            review_status="awaiting",
            family_id="F_REAP",
            funnel_stage="drafting",
            created_at=_utcnow_naive() - timedelta(hours=2),
            last_heartbeat_at=_utcnow_naive() - timedelta(hours=1),
            last_heartbeat_stage="drafter",
        )
    )
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/reap-orphans",
        headers={"X-API-Key": "test-admin-key"},
    )
    body = resp.json()
    reason = body["reaped"][0]["kill_reason"]
    assert "drafter" in reason.lower()


@pytest.mark.asyncio
async def test_endpoint_requires_admin_auth_when_admin_key_set(
    db_engine, monkeypatch
):
    """Reaper is destructive — must require admin auth."""
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
            resp = await c.post("/api/v1/admin/papers/reap-orphans")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
