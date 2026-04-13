"""Tests for the collegial review API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_profiles(client):
    resp = await client.get("/api/v1/collegial/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert "profiles" in data


@pytest.mark.asyncio
async def test_create_profile(client):
    resp = await client.post(
        "/api/v1/collegial/profiles",
        json={
            "name": "Dr. Economics",
            "expertise_area": "Labor economics",
            "perspective_description": "Focused on causal identification in labor markets.",
            "system_prompt": "You are a labor economist reviewing this paper...",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Dr. Economics"
    assert data["expertise_area"] == "Labor economics"
    assert data["active"] is True


@pytest.mark.asyncio
async def test_get_collegial_session_no_session(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "col_paper_1", "title": "Collegial Paper", "source": "ape"},
    )
    resp = await client.get("/api/v1/papers/col_paper_1/collegial-session")
    assert resp.status_code == 200
    assert resp.json()["session"] is None


@pytest.mark.asyncio
async def test_get_acknowledgments_empty(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "col_paper_2", "title": "No Acks Paper", "source": "ape"},
    )
    resp = await client.get("/api/v1/papers/col_paper_2/acknowledgments")
    assert resp.status_code == 200
    assert resp.json()["acknowledgments"] == []


@pytest.mark.asyncio
async def test_trigger_collegial_review_returns_result(client):
    """Collegial review runs even without a real paper (degrades gracefully)."""
    await client.post(
        "/api/v1/papers",
        json={"id": "col_paper_3", "title": "Review Me", "source": "ape"},
    )
    resp = await client.post(
        "/api/v1/papers/col_paper_3/collegial-review",
        json={"max_rounds": 1},
    )
    # Should return 200 (service runs, LLM calls may fail gracefully)
    assert resp.status_code == 200
