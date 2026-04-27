"""Tests for DATA_MODE strict vs permissive behaviour.

DATA_MODE=real (the default) hard-fails when no source returns real data,
preventing the pipeline from silently producing papers grounded in
synthetic placeholders. DATA_MODE=permissive preserves the legacy
fallback for local development.
"""

from __future__ import annotations

import tempfile

import pytest

from app.services.paper_generation.data_fetcher import (
    DataFetchError,
    fetch_data,
)
from app.services.paper_generation.idea_generator import ResearchIdea


def _idea_with_no_real_sources() -> ResearchIdea:
    """A research idea whose declared sources will never resolve to real fetches.

    Using a deliberately unknown source ID so the registry returns no client
    and the data fetcher exhausts every source without producing real data.
    """
    return ResearchIdea(
        title="Test idea",
        abstract="Test abstract",
        research_question="Does X cause Y?",
        identification_strategy="DiD",
        data_sources=["nonexistent_source_for_test"],
        category="test",
        country=None,
        method="DiD",
    )


# ── DATA_MODE=real ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_data_mode_real_raises_when_no_source_returns_data(monkeypatch):
    """Strict mode: no real fetch succeeded → DataFetchError."""
    monkeypatch.setattr("app.config.settings.data_mode", "real")
    monkeypatch.setattr(
        "app.services.paper_generation.data_fetcher.settings.data_mode",
        "real",
    )

    idea = _idea_with_no_real_sources()
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(DataFetchError) as excinfo:
            await fetch_data(idea, tmp)
        # Error message should explain why the user is seeing this and how
        # to opt out (only in dev).
        msg = str(excinfo.value)
        assert "No real data fetched" in msg
        assert "DATA_MODE=real" in msg
        assert "permissive" in msg


@pytest.mark.asyncio
async def test_data_mode_real_does_not_emit_placeholder_csv(monkeypatch, tmp_path):
    """Strict mode: no `placeholder.csv` is left on disk on failure."""
    monkeypatch.setattr(
        "app.services.paper_generation.data_fetcher.settings.data_mode",
        "real",
    )
    idea = _idea_with_no_real_sources()
    with pytest.raises(DataFetchError):
        await fetch_data(idea, str(tmp_path))
    # No synthetic CSV should be left behind.
    placeholder = tmp_path / "data" / "placeholder.csv"
    assert not placeholder.exists()


# ── DATA_MODE=permissive ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_data_mode_permissive_emits_placeholder_when_no_real_data(monkeypatch, tmp_path):
    """Permissive mode: synthetic placeholder CSV is produced and reported."""
    monkeypatch.setattr(
        "app.services.paper_generation.data_fetcher.settings.data_mode",
        "permissive",
    )
    idea = _idea_with_no_real_sources()
    result = await fetch_data(idea, str(tmp_path))

    assert result.success
    assert result.row_count == 100
    placeholder = tmp_path / "data" / "placeholder.csv"
    assert placeholder.exists()
    # Header check — we expect the documented synthetic schema.
    header = placeholder.read_text().splitlines()[0]
    assert header == "id,year,treatment,outcome,control_var1,control_var2"


@pytest.mark.asyncio
async def test_data_mode_permissive_logs_loud_warning(monkeypatch, tmp_path, caplog):
    """Permissive mode emits an ERROR-level log so the operator cannot
    accidentally ship synthetic-data papers without noticing."""
    import logging

    monkeypatch.setattr(
        "app.services.paper_generation.data_fetcher.settings.data_mode",
        "permissive",
    )
    idea = _idea_with_no_real_sources()
    with caplog.at_level(logging.ERROR, logger="app.services.paper_generation.data_fetcher"):
        await fetch_data(idea, str(tmp_path))
    # The warning text must reference both the mode and the safety implication.
    relevant = [r for r in caplog.records if "permissive" in r.getMessage().lower()]
    assert relevant, "Expected an ERROR log about permissive mode"
    assert any("NOT grounded" in r.getMessage() for r in relevant)


# ── Default ───────────────────────────────────────────────────────────────────


def test_data_mode_defaults_to_real():
    """Out of the box, settings.data_mode is 'real' — no env required."""
    from app.config import Settings

    fresh = Settings()
    assert fresh.data_mode == "real"
