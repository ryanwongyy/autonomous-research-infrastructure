"""Tests for the stats API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def stats_data(db_session: AsyncSession):
    """Create papers with ratings for stats queries."""
    family = PaperFamily(
        id="F1",
        name="Test Family",
        short_name="TF",
        description="For stats tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    # AI papers
    for i in range(3):
        paper = Paper(
            id=f"ai_paper_{i}",
            title=f"AI Paper {i}",
            source="ape",
            family_id="F1",
            status="published",
        )
        db_session.add(paper)
        await db_session.flush()
        rating = Rating(
            paper_id=paper.id,
            family_id="F1",
            mu=25.0 + i,
            sigma=8.0,
            conservative_rating=1.0 + i,
            elo=1500.0 + i * 100,
        )
        db_session.add(rating)

    # Benchmark papers
    for i in range(2):
        paper = Paper(
            id=f"bench_paper_{i}",
            title=f"Benchmark Paper {i}",
            source="benchmark",
            family_id="F1",
            status="published",
        )
        db_session.add(paper)
        await db_session.flush()
        rating = Rating(
            paper_id=paper.id,
            family_id="F1",
            mu=28.0 + i,
            sigma=6.0,
            conservative_rating=10.0 + i,
            elo=1600.0 + i * 100,
        )
        db_session.add(rating)

    await db_session.commit()


# ── GET /stats ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_empty_db(client):
    """Stats endpoint works on an empty database."""
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_papers"] == 0
    assert data["total_ai_papers"] == 0
    assert data["total_benchmark_papers"] == 0
    assert data["total_matches"] == 0
    assert data["ai_win_rate"] == 0.0


@pytest.mark.asyncio
async def test_stats_with_data(client, stats_data):
    """Stats reflect the seeded papers."""
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_papers"] == 5
    assert data["total_ai_papers"] == 3
    assert data["total_benchmark_papers"] == 2
    assert data["avg_elo_ai"] is not None
    assert data["avg_elo_benchmark"] is not None


@pytest.mark.asyncio
async def test_stats_response_shape(client, stats_data):
    """Stats response has the expected fields."""
    resp = await client.get("/api/v1/stats")
    data = resp.json()
    expected = {
        "total_papers",
        "total_ai_papers",
        "total_benchmark_papers",
        "total_matches",
        "total_tournament_runs",
        "ai_win_rate",
        "avg_elo_ai",
        "avg_elo_benchmark",
    }
    assert expected.issubset(set(data.keys()))


# ── GET /stats/rating-distribution ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rating_distribution_empty(client):
    """Rating distribution on empty DB returns empty arrays."""
    resp = await client.get("/api/v1/stats/rating-distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert data["elo_distribution"] == []
    assert data["conservative_distribution"] == []


@pytest.mark.asyncio
async def test_rating_distribution_with_data(client, stats_data):
    """Rating distribution buckets papers correctly."""
    resp = await client.get("/api/v1/stats/rating-distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["elo_distribution"]) > 0
    # Each bucket has the expected shape
    bucket = data["elo_distribution"][0]
    assert "bucket_start" in bucket
    assert "bucket_end" in bucket
    assert "count_ai" in bucket
    assert "count_benchmark" in bucket


@pytest.mark.asyncio
async def test_rating_distribution_custom_bucket_size(client, stats_data):
    """Custom bucket_size affects distribution granularity."""
    resp_small = await client.get("/api/v1/stats/rating-distribution?bucket_size=10")
    resp_large = await client.get("/api/v1/stats/rating-distribution?bucket_size=500")
    assert resp_small.status_code == 200
    assert resp_large.status_code == 200
    # Smaller buckets should produce more (or equal) entries
    assert len(resp_small.json()["elo_distribution"]) >= len(resp_large.json()["elo_distribution"])


# ── GET /stats/trueskill-progression ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_trueskill_progression_empty(client):
    """TrueSkill progression on empty DB returns empty data."""
    resp = await client.get("/api/v1/stats/trueskill-progression")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"] == []


@pytest.mark.asyncio
async def test_trueskill_progression_with_data_no_snapshots(client, stats_data):
    """With papers but no snapshots, returns empty data."""
    resp = await client.get("/api/v1/stats/trueskill-progression?top_n=3")
    assert resp.status_code == 200
    # No RatingSnapshot records exist, so data should be empty
    assert resp.json()["data"] == []
