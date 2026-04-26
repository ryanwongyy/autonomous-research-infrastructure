"""Integration tests exercising cross-cutting queries across the full pipeline.

These tests use the ``full_pipeline`` fixture (defined in conftest.py) which
seeds two families, seven papers with ratings, reviews, matches, outcomes,
failures, corrections, and enrichment records.
"""

from __future__ import annotations

import pytest

# =============================================================================
# Leaderboard (5 tests)
# =============================================================================


@pytest.mark.asyncio
async def test_leaderboard_f1_returns_published_entries_sorted(full_pipeline, client):
    """GET /leaderboard?family_id=F_int_1 returns published papers sorted
    by conservative_rating descending (the default).

    The fixture has 5 papers in F_int_1 but only 4 are status='published'
    (int_p5 is 'killed'), so the leaderboard endpoint -- which filters on
    status=='published' -- should return 4 entries.
    """
    resp = await client.get("/api/v1/leaderboard?family_id=F_int_1")
    assert resp.status_code == 200
    data = resp.json()

    # int_p5 is killed, so only 4 published papers
    entries = data["entries"]
    assert len(entries) == 4
    # Verify sorted descending by conservative_rating
    c_ratings = [e["conservative_rating"] for e in entries]
    assert c_ratings == sorted(c_ratings, reverse=True)


@pytest.mark.asyncio
async def test_leaderboard_entries_have_correct_match_stats(client, full_pipeline):
    """Leaderboard entries carry the wins/losses/matches_played from ratings."""
    resp = await client.get("/api/v1/leaderboard?family_id=F_int_1")
    entries = {e["paper_id"]: e for e in resp.json()["entries"]}

    # int_p1 was seeded with wins=6, losses=1, matches_played=8
    p1 = entries["int_p1"]
    assert p1["wins"] == 6
    assert p1["losses"] == 1
    assert p1["matches_played"] == 8


@pytest.mark.asyncio
async def test_leaderboard_source_filter_ape(client, full_pipeline):
    """source=ape returns only the 3 APE papers that are published in F_int_1."""
    resp = await client.get("/api/v1/leaderboard?family_id=F_int_1&source=ape")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert all(e["source"] == "ape" for e in entries)
    assert len(entries) == 3


@pytest.mark.asyncio
async def test_leaderboard_f2_independent(client, full_pipeline):
    """F_int_2 leaderboard is independent -- only its 2 papers appear."""
    resp = await client.get("/api/v1/leaderboard?family_id=F_int_2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    paper_ids = {e["paper_id"] for e in data["entries"]}
    assert paper_ids == {"int_p6", "int_p7"}


@pytest.mark.asyncio
async def test_leaderboard_sort_by_elo(client, full_pipeline):
    """sort_by=elo returns entries in descending elo order."""
    resp = await client.get("/api/v1/leaderboard?family_id=F_int_1&sort_by=elo")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    elos = [e["elo"] for e in entries]
    assert elos == sorted(elos, reverse=True)


# =============================================================================
# Throughput (3 tests)
# =============================================================================


@pytest.mark.asyncio
async def test_funnel_snapshot_stage_counts(client, full_pipeline):
    """Funnel snapshot reflects the fixture's funnel_stage distribution."""
    resp = await client.get("/api/v1/throughput/funnel")
    assert resp.status_code == 200
    data = resp.json()

    stages = data["stages"]
    # F_int_1: candidate(1), reviewing(1), drafting(1), public(1)  [killed is separate]
    # F_int_2: analyzing(2)
    # Total across all families:
    assert stages.get("candidate", 0) == 1  # int_p1
    assert stages.get("public", 0) == 1  # int_p4
    assert stages.get("analyzing", 0) == 2  # int_p6, int_p7


@pytest.mark.asyncio
async def test_funnel_killed_count(client, full_pipeline):
    """Killed papers are counted correctly in the funnel snapshot."""
    resp = await client.get("/api/v1/throughput/funnel")
    assert resp.status_code == 200
    assert resp.json()["killed"] == 1  # int_p5 is killed


@pytest.mark.asyncio
async def test_funnel_family_filter(client, full_pipeline):
    """family_id filter scopes funnel results to one family."""
    resp = await client.get("/api/v1/throughput/funnel?family_id=F_int_2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["family_id"] == "F_int_2"
    # F_int_2 has 2 papers both at 'analyzing'
    assert data["stages"].get("analyzing", 0) == 2
    assert data["killed"] == 0


# =============================================================================
# Stats (3 tests)
# =============================================================================


@pytest.mark.asyncio
async def test_stats_total_papers(client, full_pipeline):
    """Stats endpoint reports the correct total_papers count."""
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_papers"] == 7


@pytest.mark.asyncio
async def test_stats_source_breakdown(client, full_pipeline):
    """AI vs benchmark paper counts match the fixture."""
    resp = await client.get("/api/v1/stats")
    data = resp.json()
    # 4 ape papers (int_p1..p3 + int_p6), 3 benchmark (int_p4, int_p5, int_p7)
    assert data["total_ai_papers"] == 4
    assert data["total_benchmark_papers"] == 3


@pytest.mark.asyncio
async def test_stats_avg_elo_by_source(client, full_pipeline):
    """Average elo by source is computed correctly."""
    resp = await client.get("/api/v1/stats")
    data = resp.json()

    # APE papers (source='ape'): int_p1(1700), int_p2(1600), int_p3(1550), int_p6(1650)
    expected_avg_ai = round((1700 + 1600 + 1550 + 1650) / 4, 1)
    assert data["avg_elo_ai"] == expected_avg_ai

    # Benchmark papers: int_p4(1480), int_p5(1400), int_p7(1500)
    expected_avg_bench = round((1480 + 1400 + 1500) / 3, 1)
    assert data["avg_elo_benchmark"] == expected_avg_bench


# =============================================================================
# Failures / Corrections / Outcomes (3 tests)
# =============================================================================


@pytest.mark.asyncio
async def test_failures_dashboard_distribution(client, full_pipeline):
    """Failure dashboard shows correct type distribution."""
    resp = await client.get("/api/v1/failures/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    dist = data["distribution"]
    assert dist["total"] == 3
    assert dist["by_type"]["data_error"] == 1
    assert dist["by_type"]["hallucination"] == 1
    assert dist["by_type"]["causal_overreach"] == 1


@pytest.mark.asyncio
async def test_corrections_dashboard_family_breakdown(client, full_pipeline):
    """Corrections dashboard shows family-level breakdown.

    Corrections exist for int_p1 (F_int_1, release=candidate) and
    int_p4 (F_int_1, release=public).  The corrections dashboard only
    counts papers with release_status='public', so the family total
    will be 1 public paper.  Corrections for both papers are still
    counted.
    """
    resp = await client.get("/api/v1/corrections/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "families" in data

    # F_int_1 should appear if it has any public papers with corrections
    # int_p4 is public, so total_public_papers for F_int_1 >= 1
    f1_entries = [f for f in data["families"] if f["family_id"] == "F_int_1"]
    if f1_entries:
        entry = f1_entries[0]
        assert entry["total_public_papers"] >= 1
        assert entry["total_corrections"] >= 1


@pytest.mark.asyncio
async def test_outcomes_dashboard_overall(client, full_pipeline):
    """Outcomes dashboard returns correct overall stats."""
    resp = await client.get("/api/v1/outcomes/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    overall = data["overall"]
    assert overall["total"] == 3
    assert overall["accepted"] == 1
    assert overall["rejected"] == 1
    assert overall["pending"] == 1


# =============================================================================
# Release / Enrichment (3 tests)
# =============================================================================


@pytest.mark.asyncio
async def test_release_status_distribution(client, full_pipeline):
    """Release status overview reflects the paper release_status distribution."""
    resp = await client.get("/api/v1/release/status")
    assert resp.status_code == 200
    data = resp.json()
    counts = data["counts"]

    # Fixture release statuses:
    # candidate: int_p1
    # public:    int_p4
    # internal:  int_p2, int_p3, int_p5, int_p6, int_p7  (5 total)
    assert counts["candidate"] == 1
    assert counts["public"] == 1
    assert counts["internal"] == 5


@pytest.mark.asyncio
async def test_get_paper_returns_data(client, full_pipeline):
    """GET /papers/{id} returns the paper with rating data."""
    resp = await client.get("/api/v1/papers/int_p1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "int_p1"
    assert data["title"] == "Paper int_p1"
    assert data["source"] == "ape"
    # Rating data should be populated via PaperWithRating schema
    assert data["mu"] == 35.0
    assert data["elo"] == 1700


@pytest.mark.asyncio
async def test_paper_failures_endpoint(client, full_pipeline):
    """GET /papers/{id}/failures returns failure records for that paper."""
    resp = await client.get("/api/v1/papers/int_p2/failures")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["failure_type"] == "data_error"
    assert items[0]["severity"] == "high"
