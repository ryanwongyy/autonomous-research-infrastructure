"""Negative-path and boundary-value tests for critical API endpoints.

Covers error responses, invalid inputs, auth gates, and empty-data
edge cases that the happy-path test files do not exercise.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db
from app.models.paper import Paper
from app.models.paper_family import PaperFamily

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def authed_admin_client(db_engine, monkeypatch):
    """Client with admin key -- needed for admin-gated endpoints."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "test-admin-key")

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    # Patch async_session used directly inside batch.py
    monkeypatch.setattr("app.api.batch.async_session", session_factory)

    from app.main import app

    async def _test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def noauth_mutation_client(db_engine, monkeypatch):
    """Client with auth enforced but NO key header -- for 401/403 tests."""
    monkeypatch.setattr("app.config.settings.ape_api_key", "real-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "real-admin-key")

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.api.batch.async_session", session_factory)

    from app.main import app

    async def _test_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        # No X-API-Key header
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def family_and_paper(db_session: AsyncSession):
    """Seed a family and one paper for tests that need existing data."""
    family = PaperFamily(
        id="NEG_F1",
        name="Negative-Path Family",
        short_name="Neg",
        description="For negative-path tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    paper = Paper(
        id="neg_paper_001",
        title="Negative Test Paper",
        source="ape",
        family_id="NEG_F1",
        status="published",
        review_status="awaiting",
        release_status="internal",
    )
    db_session.add(paper)
    await db_session.commit()
    return {"family": family, "paper": paper}


# ============================================================================
# 1. Leaderboard  --  /api/v1/leaderboard
# ============================================================================


class TestLeaderboardNegative:
    """Negative paths for the leaderboard endpoint."""

    @pytest.mark.asyncio
    async def test_missing_family_id_returns_422(self, client):
        """family_id is required; omitting it must return 422."""
        resp = await client.get("/api/v1/leaderboard")
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_empty_family_id_returns_404(self, client):
        """Empty string family_id should either 422 or 404."""
        resp = await client.get("/api/v1/leaderboard?family_id=")
        # FastAPI treats empty string as provided; the DB lookup fails -> 404
        assert resp.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_invalid_sort_by_returns_422(self, client, family_and_paper):
        """sort_by has a regex pattern constraint; invalid values -> 422."""
        resp = await client.get("/api/v1/leaderboard?family_id=NEG_F1&sort_by=drop_table")
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_negative_offset_returns_422(self, client, family_and_paper):
        """offset has ge=0 constraint; negative -> 422."""
        resp = await client.get("/api/v1/leaderboard?family_id=NEG_F1&offset=-1")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_zero_limit_returns_422(self, client, family_and_paper):
        """limit has ge=1 constraint; 0 -> 422."""
        resp = await client.get("/api/v1/leaderboard?family_id=NEG_F1&limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_exceeds_max_returns_422(self, client, family_and_paper):
        """limit has le=250 constraint; 999 -> 422."""
        resp = await client.get("/api/v1/leaderboard?family_id=NEG_F1&limit=999")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_nonexistent_family_returns_404(self, client):
        """Querying a family that does not exist -> 404."""
        resp = await client.get("/api/v1/leaderboard?family_id=DOES_NOT_EXIST")
        assert resp.status_code == 404
        assert "detail" in resp.json()


# ============================================================================
# 2. Papers  --  /api/v1/papers/{paper_id}
# ============================================================================


class TestPapersNegative:
    """Negative paths for the papers endpoints."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_uuid_returns_404(self, client):
        """GET with a random UUID-like ID that does not exist -> 404."""
        random_id = f"apep_{uuid.uuid4().hex[:8]}"
        resp = await client.get(f"/api/v1/papers/{random_id}")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"] == "Paper not found"

    @pytest.mark.asyncio
    async def test_get_completely_bogus_id_returns_404(self, client):
        """GET with a nonsensical string returns 404 (no paper found)."""
        resp = await client.get("/api/v1/papers/!!!invalid!!!")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_paper_missing_title_returns_422(self, client):
        """Title is required on PaperCreate; omitting it -> 422."""
        resp = await client.post(
            "/api/v1/papers",
            json={"source": "ape"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_paper_title_too_long_returns_422(self, client):
        """Title max_length=500; exceeding it -> 422."""
        resp = await client.post(
            "/api/v1/papers",
            json={"title": "x" * 501, "source": "ape"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_paper_empty_json_body_returns_422(self, client):
        """POST with an empty JSON object -> 422 (missing required title)."""
        resp = await client.post("/api/v1/papers", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_paper_non_json_body_returns_422(self, client):
        """POST with a non-JSON content type -> 422."""
        resp = await client.post(
            "/api/v1/papers",
            content=b"not json",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_export_paper_nonexistent_returns_404(self, client):
        """Exporting a paper that does not exist -> 404."""
        resp = await client.get("/api/v1/papers/nonexistent/export?format=pdf")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_paper_invalid_format_returns_422(self, client, family_and_paper):
        """Export format has a pattern constraint (pdf|tex); 'docx' -> 422."""
        resp = await client.get("/api/v1/papers/neg_paper_001/export?format=docx")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_papers_limit_zero_returns_422(self, client):
        """limit ge=1 on paper list; 0 -> 422."""
        resp = await client.get("/api/v1/papers?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_papers_negative_offset_returns_422(self, client):
        """offset ge=0 on paper list; -5 -> 422."""
        resp = await client.get("/api/v1/papers?offset=-5")
        assert resp.status_code == 422


# ============================================================================
# 3. Batch endpoints  --  /api/v1/batch/*
# ============================================================================


class TestBatchNegative:
    """Auth gating and validation for batch endpoints."""

    @pytest.mark.asyncio
    async def test_seed_families_without_auth_returns_401(self, noauth_mutation_client):
        """POST /batch/seed-families without any API key -> 401."""
        resp = await noauth_mutation_client.post("/api/v1/batch/seed-families")
        assert resp.status_code == 401
        assert "detail" in resp.json()

    @pytest.mark.asyncio
    async def test_seed_families_with_wrong_key_returns_403(self, db_engine, monkeypatch):
        """POST /batch/seed-families with the regular (non-admin) key -> 403."""
        monkeypatch.setattr("app.config.settings.ape_api_key", "regular-key")
        monkeypatch.setattr("app.config.settings.ape_admin_key", "admin-key")

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr("app.api.batch.async_session", session_factory)
        from app.main import app

        async def _test_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _test_db
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-API-Key": "regular-key"},
        ) as c:
            resp = await c.post("/api/v1/batch/seed-families")
        app.dependency_overrides.clear()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_generate_count_zero_returns_422(self, authed_admin_client):
        """POST /batch/generate with count=0 (below ge=1) -> 422."""
        resp = await authed_admin_client.post("/api/v1/batch/generate", json={"count": 0})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_count_too_large_returns_422(self, authed_admin_client):
        """POST /batch/generate with count=100 (above le=10) -> 422."""
        resp = await authed_admin_client.post("/api/v1/batch/generate", json={"count": 100})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_negative_count_returns_422(self, authed_admin_client):
        """POST /batch/generate with count=-1 -> 422."""
        resp = await authed_admin_client.post("/api/v1/batch/generate", json={"count": -1})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_non_integer_count_returns_422(self, authed_admin_client):
        """POST /batch/generate with count='abc' -> 422."""
        resp = await authed_admin_client.post("/api/v1/batch/generate", json={"count": "abc"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_review_pending_without_auth_returns_401(self, noauth_mutation_client):
        """POST /batch/review-pending without key -> 401."""
        resp = await noauth_mutation_client.post("/api/v1/batch/review-pending")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_batch_promote_without_auth_returns_401(self, noauth_mutation_client):
        """POST /batch/promote without key -> 401."""
        resp = await noauth_mutation_client.post("/api/v1/batch/promote")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_batch_tournament_without_auth_returns_401(self, noauth_mutation_client):
        """POST /batch/tournament without key -> 401."""
        resp = await noauth_mutation_client.post("/api/v1/batch/tournament")
        assert resp.status_code == 401


# ============================================================================
# 4. Tournament  --  /api/v1/tournament/*
# ============================================================================


class TestTournamentNegative:
    """Auth and validation for tournament endpoints."""

    @pytest.mark.asyncio
    async def test_trigger_tournament_without_auth_returns_401(self, noauth_mutation_client):
        """POST /tournament/run without any API key -> 401."""
        resp = await noauth_mutation_client.post("/api/v1/tournament/run?family_id=F1")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_trigger_tournament_with_wrong_key_returns_403(self, client, monkeypatch):
        """POST /tournament/run with regular key (not admin) -> 403."""
        monkeypatch.setattr("app.config.settings.ape_api_key", "regular-key")
        monkeypatch.setattr("app.config.settings.ape_admin_key", "admin-key")
        resp = await client.post(
            "/api/v1/tournament/run?family_id=F1",
            headers={"X-API-Key": "regular-key"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_trigger_tournament_missing_family_id_returns_422(self, authed_admin_client):
        """POST /tournament/run without family_id query param -> 422."""
        resp = await authed_admin_client.post("/api/v1/tournament/run")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_trigger_tournament_nonexistent_family_returns_404(self, authed_admin_client):
        """POST /tournament/run for a family that does not exist -> 404."""
        resp = await authed_admin_client.post("/api/v1/tournament/run?family_id=DOES_NOT_EXIST")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    @pytest.mark.asyncio
    async def test_get_tournament_run_nonexistent_returns_404(self, client):
        """GET /tournament/runs/{id} with a bogus run ID -> 404."""
        resp = await client.get("/api/v1/tournament/runs/999999")
        assert resp.status_code == 404


# ============================================================================
# 5. Sources  --  /api/v1/sources/*
# ============================================================================


class TestSourcesNegative:
    """Negative paths for source endpoints."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_source_returns_404(self, client):
        """GET /sources/nonexistent -> 404."""
        resp = await client.get("/api/v1/sources/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body

    @pytest.mark.asyncio
    async def test_get_snapshots_nonexistent_source_returns_404(self, client):
        """GET /sources/nonexistent/snapshots -> 404 (source not found)."""
        resp = await client.get("/api/v1/sources/nonexistent/snapshots")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_sources_empty_returns_gracefully(self, client):
        """GET /sources on an empty DB returns 200 with total=0."""
        resp = await client.get("/api/v1/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["sources"] == []


# ============================================================================
# 6. Families  --  /api/v1/families/*
# ============================================================================


class TestFamiliesNegative:
    """Negative paths for family endpoints."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_family_returns_404(self, client):
        """GET /families/nonexistent -> 404."""
        resp = await client.get("/api/v1/families/NONEXISTENT")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        assert "NONEXISTENT" in body["detail"]

    @pytest.mark.asyncio
    async def test_get_family_empty_id_returns_404(self, client):
        """GET /families/ with trailing slash is a different route."""
        # FastAPI's path param won't match an empty segment; expect 404 or 307
        resp = await client.get("/api/v1/families/")
        # Either a redirect to /families or method not allowed
        assert resp.status_code in (200, 307, 404)

    @pytest.mark.asyncio
    async def test_list_families_empty_db_returns_200(self, client):
        """GET /families on an empty DB returns 200 with empty list."""
        resp = await client.get("/api/v1/families")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["families"] == []


# ============================================================================
# 7. Release  --  /api/v1/papers/{id}/release/*
# ============================================================================


class TestReleaseNegative:
    """Negative paths for release transition endpoints."""

    @pytest.mark.asyncio
    async def test_transition_nonexistent_paper_returns_404(self, client):
        """POST transition for a paper that does not exist -> 404."""
        resp = await client.post("/api/v1/papers/NOPE/release/transition?target_status=candidate")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_transition_invalid_target_status_returns_422(self, client, family_and_paper):
        """target_status has a Literal constraint; invalid value -> 422."""
        resp = await client.post(
            "/api/v1/papers/neg_paper_001/release/transition?target_status=bogus_status"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_transition_missing_target_status_returns_422(self, client, family_and_paper):
        """target_status is required; omitting it -> 422."""
        resp = await client.post("/api/v1/papers/neg_paper_001/release/transition")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_transition_force_without_approved_by_returns_400(self, client, family_and_paper):
        """Force=true but no approved_by -> 400."""
        resp = await client.post(
            "/api/v1/papers/neg_paper_001/release/transition?target_status=candidate&force=true"
        )
        assert resp.status_code == 400
        assert "approved_by" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_preconditions_nonexistent_paper_returns_404(self, client):
        """GET preconditions for nonexistent paper -> 404."""
        resp = await client.get("/api/v1/papers/NOPE/release/preconditions?target_status=candidate")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_preconditions_invalid_target_returns_422(self, client, family_and_paper):
        """Preconditions with invalid target_status -> 422."""
        resp = await client.get(
            "/api/v1/papers/neg_paper_001/release/preconditions?target_status=nonsense"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_preconditions_missing_target_returns_422(self, client, family_and_paper):
        """Preconditions without target_status query param -> 422."""
        resp = await client.get("/api/v1/papers/neg_paper_001/release/preconditions")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_release_status_nonexistent_paper_returns_404(self, client):
        """GET /papers/{id}/release for nonexistent paper -> 404."""
        resp = await client.get("/api/v1/papers/NOPE_999/release")
        assert resp.status_code == 404


# ============================================================================
# 8. Stats  --  /api/v1/stats/*
# ============================================================================


class TestStatsNegative:
    """Boundary/empty-data tests for stats endpoints."""

    @pytest.mark.asyncio
    async def test_rating_distribution_empty_db_returns_200(self, client):
        """GET /stats/rating-distribution with no data -> 200 with empty lists."""
        resp = await client.get("/api/v1/stats/rating-distribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["elo_distribution"] == []
        assert data["conservative_distribution"] == []

    @pytest.mark.asyncio
    async def test_rating_distribution_bucket_too_small_returns_422(self, client):
        """bucket_size has ge=5.0; 1.0 -> 422."""
        resp = await client.get("/api/v1/stats/rating-distribution?bucket_size=1.0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rating_distribution_bucket_too_large_returns_422(self, client):
        """bucket_size has le=1000.0; 5000 -> 422."""
        resp = await client.get("/api/v1/stats/rating-distribution?bucket_size=5000")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_stats_empty_db_returns_zeros(self, client):
        """GET /stats with no data returns 200 with zero counters."""
        resp = await client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_papers"] == 0
        assert data["total_matches"] == 0
        assert data["ai_win_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_trueskill_progression_empty_returns_200(self, client):
        """GET /stats/trueskill-progression with no data -> 200 empty."""
        resp = await client.get("/api/v1/stats/trueskill-progression")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_trueskill_progression_top_n_zero_returns_422(self, client):
        """top_n has ge=1; 0 -> 422."""
        resp = await client.get("/api/v1/stats/trueskill-progression?top_n=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_trueskill_progression_top_n_too_large_returns_422(self, client):
        """top_n has le=50; 999 -> 422."""
        resp = await client.get("/api/v1/stats/trueskill-progression?top_n=999")
        assert resp.status_code == 422


# ============================================================================
# 9. Cross-cutting: mutation auth middleware
# ============================================================================


class TestMutationAuthMiddleware:
    """The MutationAuthMiddleware rejects mutating requests without a key."""

    @pytest.mark.asyncio
    async def test_post_paper_without_key_returns_401(self, noauth_mutation_client):
        """POST /papers without API key -> 401."""
        resp = await noauth_mutation_client.post(
            "/api/v1/papers",
            json={"title": "Should fail", "source": "ape"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or missing API key"

    @pytest.mark.asyncio
    async def test_get_endpoints_bypass_auth(self, noauth_mutation_client):
        """GET requests do not need an API key (safe methods pass through)."""
        resp = await noauth_mutation_client.get("/api/v1/papers")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_wrong_key_returns_401(self, db_engine, monkeypatch):
        """A wrong API key should produce 401."""
        monkeypatch.setattr("app.config.settings.ape_api_key", "correct-key")
        monkeypatch.setattr("app.config.settings.ape_admin_key", "admin-key")

        session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        from app.main import app

        async def _test_db():
            async with session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _test_db
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"X-API-Key": "wrong-key"},
        ) as c:
            resp = await c.post(
                "/api/v1/papers",
                json={"title": "Should fail", "source": "ape"},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 401
