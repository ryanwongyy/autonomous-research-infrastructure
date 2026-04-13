"""Tests for the papers API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_papers_empty(client):
    resp = await client.get("/api/v1/papers")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_paper(client):
    resp = await client.post(
        "/api/v1/papers",
        json={"title": "AI Governance in Federal Procurement", "source": "ape"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "AI Governance in Federal Procurement"
    assert data["source"] == "ape"
    assert data["id"].startswith("apep_")
    assert data["status"] == "published"  # API sets status=published on create
    assert data["review_status"] == "awaiting"


@pytest.mark.asyncio
async def test_create_paper_with_id(client):
    resp = await client.post(
        "/api/v1/papers",
        json={"id": "custom_001", "title": "Custom ID Paper", "source": "benchmark"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "custom_001"


@pytest.mark.asyncio
async def test_create_duplicate_paper(client):
    paper = {"id": "dup_test", "title": "Original", "source": "ape"}
    resp1 = await client.post("/api/v1/papers", json=paper)
    assert resp1.status_code == 200

    resp2 = await client.post("/api/v1/papers", json=paper)
    assert resp2.status_code == 500  # IntegrityError on duplicate PK


@pytest.mark.asyncio
async def test_get_paper_by_id(client):
    create = await client.post(
        "/api/v1/papers",
        json={"title": "Lookup Test", "source": "ape"},
    )
    paper_id = create.json()["id"]

    resp = await client.get(f"/api/v1/papers/{paper_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Lookup Test"


@pytest.mark.asyncio
async def test_get_nonexistent_paper(client):
    resp = await client.get("/api/v1/papers/does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_papers_with_filters(client):
    await client.post(
        "/api/v1/papers",
        json={"title": "Paper A", "source": "ape", "category": "regulation"},
    )
    await client.post(
        "/api/v1/papers",
        json={"title": "Paper B", "source": "benchmark", "category": "corporate"},
    )

    resp_ape = await client.get("/api/v1/papers?source=ape")
    assert resp_ape.status_code == 200
    titles = [p["title"] for p in resp_ape.json()]
    assert "Paper A" in titles
    # Paper B has source=benchmark so should be excluded
    assert "Paper B" not in titles


@pytest.mark.asyncio
async def test_import_papers(client):
    resp = await client.post(
        "/api/v1/papers/import",
        json={
            "papers": [
                {"title": "Imported 1", "source": "ape"},
                {"title": "Imported 2", "source": "ape"},
                {"title": "Imported 3", "source": "ape"},
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert all(p["source"] == "ape" for p in data)


@pytest.mark.asyncio
async def test_import_empty_list(client):
    resp = await client.post(
        "/api/v1/papers/import",
        json={"papers": []},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_paper_pagination(client):
    # Create several papers
    for i in range(5):
        await client.post(
            "/api/v1/papers",
            json={"title": f"Paginated {i}", "source": "ape"},
        )

    resp = await client.get("/api/v1/papers?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp2 = await client.get("/api/v1/papers?limit=2&offset=2")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 2
