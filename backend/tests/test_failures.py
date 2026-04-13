"""Tests for the failure taxonomy API endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_failure(client):
    resp = await client.post(
        "/api/v1/failures",
        json={
            "paper_id": "fail_paper_1",
            "failure_type": "data_error",
            "severity": "high",
            "detection_stage": "review_layer_1",
            "root_cause_category": "stale_data",
            "resolution": "Re-fetched source data",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["failure_type"] == "data_error"
    assert data["severity"] == "high"


@pytest.mark.asyncio
async def test_create_failure_invalid_type(client):
    resp = await client.post(
        "/api/v1/failures",
        json={
            "failure_type": "unknown_type",
            "severity": "high",
            "detection_stage": "review",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_failure_invalid_severity(client):
    resp = await client.post(
        "/api/v1/failures",
        json={
            "failure_type": "logic_error",
            "severity": "extreme",
            "detection_stage": "review",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_paper_failures(client):
    # Create a paper and some failures
    await client.post(
        "/api/v1/papers",
        json={"id": "fail_paper_2", "title": "Failure Paper", "source": "ape"},
    )
    await client.post(
        "/api/v1/failures",
        json={
            "paper_id": "fail_paper_2",
            "failure_type": "hallucination",
            "severity": "critical",
            "detection_stage": "review_layer_3",
        },
    )
    await client.post(
        "/api/v1/failures",
        json={
            "paper_id": "fail_paper_2",
            "failure_type": "causal_overreach",
            "severity": "medium",
            "detection_stage": "review_layer_2",
        },
    )

    resp = await client.get("/api/v1/papers/fail_paper_2/failures")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert {f["failure_type"] for f in items} == {"hallucination", "causal_overreach"}


@pytest.mark.asyncio
async def test_failures_dashboard(client):
    resp = await client.get("/api/v1/failures/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "distribution" in data
    assert "trends" in data
