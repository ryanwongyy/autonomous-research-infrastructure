"""Tests for the corrections API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_correction(client):
    # Create a paper first
    paper = await client.post(
        "/api/v1/papers",
        json={"id": "corr_paper_1", "title": "Paper With Correction", "source": "ape"},
    )
    assert paper.status_code == 200

    resp = await client.post(
        "/api/v1/papers/corr_paper_1/corrections",
        json={
            "correction_type": "erratum",
            "description": "Fixed table 3 calculation error",
            "corrected_at": "2026-04-01T00:00:00",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == "corr_paper_1"
    assert data["correction_type"] == "erratum"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_list_corrections_empty(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "corr_paper_2", "title": "Clean Paper", "source": "ape"},
    )
    resp = await client.get("/api/v1/papers/corr_paper_2/corrections")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_corrections_after_create(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "corr_paper_3", "title": "Multi Correction", "source": "ape"},
    )
    await client.post(
        "/api/v1/papers/corr_paper_3/corrections",
        json={
            "correction_type": "erratum",
            "description": "First fix",
            "corrected_at": "2026-03-01T00:00:00",
        },
    )
    await client.post(
        "/api/v1/papers/corr_paper_3/corrections",
        json={
            "correction_type": "update",
            "description": "Second fix",
            "corrected_at": "2026-04-01T00:00:00",
        },
    )

    resp = await client.get("/api/v1/papers/corr_paper_3/corrections")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert {c["correction_type"] for c in items} == {"erratum", "update"}


@pytest.mark.asyncio
async def test_create_correction_invalid_date(client):
    await client.post(
        "/api/v1/papers",
        json={"id": "corr_paper_4", "title": "Bad Date", "source": "ape"},
    )
    resp = await client.post(
        "/api/v1/papers/corr_paper_4/corrections",
        json={
            "correction_type": "retraction",
            "description": "Bad date test",
            "corrected_at": "not-a-date",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_corrections_dashboard(client):
    resp = await client.get("/api/v1/corrections/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "families" in data
