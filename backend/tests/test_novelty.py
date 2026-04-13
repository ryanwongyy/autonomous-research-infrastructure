"""Tests for the novelty check API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_novelty_check_none(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "nov_paper_1", "title": "Novelty Paper", "source": "ape"},
    )
    resp = await client.get("/api/v1/papers/nov_paper_1/novelty-check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "nov_paper_1"
    assert data["check"] is None


@pytest.mark.asyncio
async def test_trigger_novelty_check(client):
    """Trigger novelty check on a paper with no lock artifact — defaults to 'novel'."""
    await client.post(
        "/api/v1/papers",
        json={"id": "nov_paper_2", "title": "Check Novelty", "source": "ape"},
    )
    resp = await client.post("/api/v1/papers/nov_paper_2/novelty-check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "novel"
    assert data["checked_against_count"] == 0
    assert data["paper_id"] == "nov_paper_2"


@pytest.mark.asyncio
async def test_trigger_novelty_check_nonexistent_paper(client):
    resp = await client.post("/api/v1/papers/nonexistent_999/novelty-check")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_novelty_check_persists(client):
    """After triggering, GET should return the check."""
    await client.post(
        "/api/v1/papers",
        json={"id": "nov_paper_3", "title": "Persistent Check", "source": "ape"},
    )
    await client.post("/api/v1/papers/nov_paper_3/novelty-check")

    resp = await client.get("/api/v1/papers/nov_paper_3/novelty-check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["check"] is not None
    assert data["check"]["verdict"] == "novel"
