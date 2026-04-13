"""Tests for the expert reviews API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_expert_review(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "exp_paper_1", "title": "Expert Reviewed Paper", "source": "ape"},
    )

    resp = await client.post(
        "/api/v1/papers/exp_paper_1/expert-reviews",
        json={
            "expert_name": "Dr. Jane Smith",
            "affiliation": "MIT",
            "review_date": "2026-04-10T00:00:00",
            "overall_score": 4,
            "methodology_score": 5,
            "contribution_score": 3,
            "notes": "Strong methodology, moderate novelty.",
            "is_pre_submission": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["expert_name"] == "Dr. Jane Smith"
    assert data["overall_score"] == 4
    assert data["paper_id"] == "exp_paper_1"


@pytest.mark.asyncio
async def test_list_expert_reviews_empty(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "exp_paper_2", "title": "No Reviews Yet", "source": "ape"},
    )
    resp = await client.get("/api/v1/papers/exp_paper_2/expert-reviews")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_expert_reviews_after_create(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "exp_paper_3", "title": "Two Reviews", "source": "ape"},
    )
    await client.post(
        "/api/v1/papers/exp_paper_3/expert-reviews",
        json={
            "expert_name": "Dr. A",
            "review_date": "2026-03-01T00:00:00",
            "overall_score": 3,
        },
    )
    await client.post(
        "/api/v1/papers/exp_paper_3/expert-reviews",
        json={
            "expert_name": "Dr. B",
            "review_date": "2026-04-01T00:00:00",
            "overall_score": 5,
        },
    )

    resp = await client.get("/api/v1/papers/exp_paper_3/expert-reviews")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_create_expert_review_invalid_date(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "exp_paper_4", "title": "Bad Date", "source": "ape"},
    )
    resp = await client.post(
        "/api/v1/papers/exp_paper_4/expert-reviews",
        json={
            "expert_name": "Dr. C",
            "review_date": "invalid",
            "overall_score": 3,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_expert_review_score_bounds(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "exp_paper_5", "title": "Score Bounds", "source": "ape"},
    )
    # Score too high
    resp = await client.post(
        "/api/v1/papers/exp_paper_5/expert-reviews",
        json={
            "expert_name": "Dr. D",
            "review_date": "2026-04-10T00:00:00",
            "overall_score": 6,
        },
    )
    assert resp.status_code == 422

    # Score too low
    resp = await client.post(
        "/api/v1/papers/exp_paper_5/expert-reviews",
        json={
            "expert_name": "Dr. D",
            "review_date": "2026-04-10T00:00:00",
            "overall_score": 0,
        },
    )
    assert resp.status_code == 422
