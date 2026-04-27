"""Tests for the config API endpoints (GET/PUT /config/domains, GET /config/models)."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain_config import DomainConfig


@pytest_asyncio.fixture
async def domain_data(db_session: AsyncSession):
    """Create domain configs for testing."""
    d1 = DomainConfig(
        id="ai_governance",
        name="AI Governance",
        description="Policy research on AI regulation",
        analysis_tool="python",
        judge_model="gemini-2.0-flash",
        generation_model="claude-opus-4-6",
        categories=json.dumps([{"slug": "regulation", "name": "Regulation"}]),
        methods=json.dumps(["meta-analysis", "case-study"]),
        active=True,
    )
    d2 = DomainConfig(
        id="climate_policy",
        name="Climate Policy",
        description="Research on climate governance",
        analysis_tool="R",
        judge_model="gpt-4o",
        generation_model="gpt-4o",
        categories=json.dumps([{"slug": "mitigation", "name": "Mitigation"}]),
        methods=json.dumps(["regression"]),
        active=True,
    )
    d_inactive = DomainConfig(
        id="deprecated_domain",
        name="Deprecated Domain",
        description="No longer active",
        analysis_tool="python",
        judge_model="gemini-2.0-flash",
        generation_model="claude-opus-4-6",
        active=False,
    )
    db_session.add_all([d1, d2, d_inactive])
    await db_session.commit()
    return [d1, d2, d_inactive]


# -- GET /config/domains -------------------------------------------------------


@pytest.mark.asyncio
async def test_list_domains_empty(client):
    resp = await client.get("/api/v1/config/domains")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_domains(client, domain_data):
    resp = await client.get("/api/v1/config/domains")
    assert resp.status_code == 200
    data = resp.json()
    # All 3 returned (no active_only filter on this endpoint)
    assert len(data) == 3
    ids = [d["id"] for d in data]
    assert "ai_governance" in ids
    assert "deprecated_domain" in ids


@pytest.mark.asyncio
async def test_list_domains_response_shape(client, domain_data):
    resp = await client.get("/api/v1/config/domains")
    assert resp.status_code == 200
    item = next(d for d in resp.json() if d["id"] == "ai_governance")
    assert item["name"] == "AI Governance"
    assert item["judge_model"] == "gemini-2.0-flash"
    assert item["generation_model"] == "claude-opus-4-6"
    assert isinstance(item["categories"], list)
    assert item["categories"][0]["slug"] == "regulation"
    assert isinstance(item["methods"], list)
    assert item["active"] is True


# -- GET /config/domains/{domain_id} -------------------------------------------


@pytest.mark.asyncio
async def test_get_domain_detail(client, domain_data):
    resp = await client.get("/api/v1/config/domains/ai_governance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "ai_governance"
    assert data["description"] == "Policy research on AI regulation"


@pytest.mark.asyncio
async def test_get_domain_not_found(client):
    resp = await client.get("/api/v1/config/domains/nonexistent")
    assert resp.status_code == 404


# -- PUT /config/domains/{domain_id} -------------------------------------------


@pytest.mark.asyncio
async def test_update_domain(client, domain_data):
    resp = await client.put(
        "/api/v1/config/domains/ai_governance",
        json={"name": "AI Governance v2", "active": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AI Governance v2"
    assert data["active"] is False


@pytest.mark.asyncio
async def test_update_domain_not_found(client):
    resp = await client.put(
        "/api/v1/config/domains/nonexistent",
        json={"name": "Nope"},
    )
    assert resp.status_code == 404


# -- GET /config/models --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_models(client):
    resp = await client.get("/api/v1/config/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "anthropic" in data["providers"]
    assert "openai" in data["providers"]
    assert "google" in data["providers"]
    assert isinstance(data["providers"]["anthropic"]["models"], list)
