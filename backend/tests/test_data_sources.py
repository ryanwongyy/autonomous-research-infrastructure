"""Tests for the data source registry and client dispatch."""

from __future__ import annotations

import pytest

from app.services.data_sources.base import FetchParams, FetchResult
from app.services.data_sources.registry import (
    fetch_from_source,
    get_source,
    list_available_sources,
)


def test_list_available_sources():
    sources = list_available_sources()
    assert "federal_register" in sources
    assert "edgar" in sources
    assert "usaspending" in sources
    assert "openalex" in sources
    assert "regulations_gov" in sources
    assert "courtlistener" in sources


def test_get_known_source():
    client = get_source("federal_register")
    assert client is not None
    assert client.source_id == "federal_register"


def test_get_unknown_source_returns_none():
    client = get_source("nonexistent_source")
    assert client is None


def test_get_source_with_api_key():
    client = get_source("regulations_gov", api_key="my-key")
    assert client is not None
    assert client.api_key == "my-key"


def test_lazy_loaded_sources():
    """Regulations.gov and CourtListener are lazily imported."""
    client = get_source("regulations_gov")
    assert client is not None
    assert client.source_id == "regulations_gov"

    client2 = get_source("courtlistener")
    assert client2 is not None
    assert client2.source_id == "courtlistener"


@pytest.mark.asyncio
async def test_fetch_unknown_source_returns_error(tmp_path):
    result = await fetch_from_source("nonexistent", FetchParams(), tmp_path)
    assert not result.success
    assert "No API client" in result.error


@pytest.mark.asyncio
async def test_regulations_gov_needs_key(tmp_path):
    """Regulations.gov should fail gracefully without an API key."""
    result = await fetch_from_source("regulations_gov", FetchParams(), tmp_path)
    assert not result.success
    assert "API key" in result.error


@pytest.mark.asyncio
async def test_courtlistener_needs_key(tmp_path):
    """CourtListener should fail gracefully without an API key."""
    result = await fetch_from_source("courtlistener", FetchParams(), tmp_path)
    assert not result.success
    assert "API key" in result.error


# ── supports_query keyword matching ────────────────────────────────────────


def test_federal_register_supports_regulation():
    client = get_source("federal_register")
    assert client.supports_query("federal regulation of AI systems")
    assert not client.supports_query("basketball scores")


def test_edgar_supports_corporate():
    client = get_source("edgar")
    assert client.supports_query("corporate disclosure of AI risks")
    assert not client.supports_query("weather forecast")


def test_openalex_supports_research():
    client = get_source("openalex")
    assert client.supports_query("academic research on AI governance")
    assert not client.supports_query("grocery prices")


def test_usaspending_supports_procurement():
    client = get_source("usaspending")
    assert client.supports_query("federal spending on AI contracts")
    assert not client.supports_query("movie reviews")


# ── FetchParams / FetchResult dataclass tests ──────────────────────────────


def test_fetch_params_defaults():
    p = FetchParams()
    assert p.max_records == 1000
    assert p.query is None
    assert p.extra == {}


def test_fetch_result_success():
    r = FetchResult(success=True, file_path="/tmp/test.csv", row_count=42)
    assert r.success
    assert r.row_count == 42


def test_fetch_result_failure():
    r = FetchResult(success=False, error="Connection timeout")
    assert not r.success
    assert r.error == "Connection timeout"
