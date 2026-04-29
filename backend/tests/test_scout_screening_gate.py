"""Tests for Scout's screening gate logic.

Production run #25110421840 demonstrated that Claude rates fresh ideas at
composite ~3.0-3.2 with at least one of {novelty, data_adequacy} at 2.
The previous AND-gate (`composite >= X AND novelty >= Y AND data >= Z`)
was provably blocking ideas the composite floor accepted.

These tests verify:
  - Default mode (strict=False) gates on composite alone — ideas with
    composite >= 3.0 pass, regardless of low per-dimension scores.
  - Strict mode (strict=True) re-imposes the per-dimension floors,
    matching pre-PR behaviour.
  - The screening output exposes per-dimension scores, thresholds, and
    the strict-flag state for downstream consumers.
"""

from __future__ import annotations

import pytest

from app.services.paper_generation.roles.scout import screen_idea


class _FakeProvider:
    """Stand-in LLMProvider that returns a fixed JSON response."""

    def __init__(self, response_text: str):
        self._response_text = response_text

    async def complete(self, **_kwargs) -> str:  # noqa: D401, ANN003
        return self._response_text


def _llm_response(scores: dict[str, int]) -> str:
    """Build the JSON response shape Scout's parser expects."""
    import json

    scores_dict = {
        dim: {"score": val, "reason": f"reason for {dim}"}
        for dim, val in scores.items()
    }
    return json.dumps(
        {
            "scores": scores_dict,
            "weighted_composite": 0.0,  # recomputed server-side
            "pass": True,  # ignored — server recomputes
            "summary": "test",
        }
    )


# ── Composite-only gate (default behaviour) ─────────────────────────────────


@pytest.mark.asyncio
async def test_default_gate_is_composite_only(monkeypatch, db_session):
    """An idea with composite >= floor passes even when novelty/data are low.

    Mirrors the production case from run #25110421840: composite 3.20,
    novelty 2 (or data 2). Old AND-gate rejected; new composite-only gate
    accepts so the rest of the pipeline can run.
    """
    # Configure thresholds explicitly so the test is independent of
    # default-value drift.
    monkeypatch.setattr("app.config.settings.scout_screen_min_composite", 3.0)
    monkeypatch.setattr("app.config.settings.scout_screen_strict_per_dimension", False)
    # Also patch the imports inside the scout module (its `settings`
    # binding is captured at import time).
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_composite",
        3.0,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_strict_per_dimension",
        False,
    )

    # Scores: importance=4, novelty=2, data=2, infcred=4, venue=4, exec=4.
    # Weighted composite: 0.25*4 + 0.20*2 + 0.20*2 + 0.20*4 + 0.10*4 + 0.05*4
    #                   = 1.00 + 0.40 + 0.40 + 0.80 + 0.40 + 0.20 = 3.20
    fake_response = _llm_response(
        {
            "importance": 4,
            "novelty": 2,
            "data_adequacy": 2,
            "inferential_credibility": 4,
            "venue_fit": 4,
            "execution_burden": 4,
        }
    )
    provider = _FakeProvider(fake_response)

    result = await screen_idea(
        session=db_session,
        idea_card={"research_question": "test"},
        provider=provider,
    )

    assert abs(result["weighted_composite"] - 3.20) < 0.01
    assert result["pass"] is True, (
        "Composite-only gate should accept composite=3.20 even with "
        "novelty=2 and data_adequacy=2"
    )
    assert result["thresholds"]["strict_per_dimension"] is False


@pytest.mark.asyncio
async def test_default_gate_rejects_below_composite_floor(monkeypatch, db_session):
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_composite",
        3.0,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_strict_per_dimension",
        False,
    )
    # Composite: all 2s = 2.0 weighted.
    fake = _FakeProvider(
        _llm_response(
            {
                "importance": 2,
                "novelty": 2,
                "data_adequacy": 2,
                "inferential_credibility": 2,
                "venue_fit": 2,
                "execution_burden": 2,
            }
        )
    )
    result = await screen_idea(
        session=db_session, idea_card={"research_question": "weak"}, provider=fake
    )
    assert result["weighted_composite"] < 3.0
    assert result["pass"] is False


# ── Strict mode (legacy behaviour, opt-in) ──────────────────────────────────


@pytest.mark.asyncio
async def test_strict_mode_rejects_low_novelty(monkeypatch, db_session):
    """In strict mode, the composite-passes-but-novelty=2 case is rejected
    just like before the PR (so the legacy gate is preserved as opt-in)."""
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_composite",
        3.0,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_novelty",
        3,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_data_adequacy",
        3,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_strict_per_dimension",
        True,
    )
    # Same scores as the composite-only happy path: composite=3.20 but
    # novelty=2.
    fake = _FakeProvider(
        _llm_response(
            {
                "importance": 4,
                "novelty": 2,
                "data_adequacy": 2,
                "inferential_credibility": 4,
                "venue_fit": 4,
                "execution_burden": 4,
            }
        )
    )
    result = await screen_idea(
        session=db_session, idea_card={"research_question": "x"}, provider=fake
    )
    assert abs(result["weighted_composite"] - 3.20) < 0.01
    assert result["pass"] is False
    assert result["thresholds"]["strict_per_dimension"] is True


@pytest.mark.asyncio
async def test_strict_mode_accepts_when_all_floors_met(monkeypatch, db_session):
    """Strict mode passes ideas that clear ALL three floors simultaneously."""
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_composite",
        3.0,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_novelty",
        3,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_data_adequacy",
        3,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_strict_per_dimension",
        True,
    )
    # All 4s: composite=4.0, novelty=4, data=4 — every floor met.
    fake = _FakeProvider(
        _llm_response(
            {
                "importance": 4,
                "novelty": 4,
                "data_adequacy": 4,
                "inferential_credibility": 4,
                "venue_fit": 4,
                "execution_burden": 4,
            }
        )
    )
    result = await screen_idea(
        session=db_session, idea_card={"research_question": "x"}, provider=fake
    )
    assert result["pass"] is True


# ── Surfaced thresholds + scores ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_thresholds_surfaced_in_result(monkeypatch, db_session):
    """The screening dict exposes the gate config so downstream consumers
    can see exactly what was required (composite floor, per-dim floors,
    strict flag)."""
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_composite",
        2.5,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_novelty",
        2,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_min_data_adequacy",
        2,
    )
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_strict_per_dimension",
        False,
    )
    fake = _FakeProvider(
        _llm_response(
            {
                "importance": 3,
                "novelty": 3,
                "data_adequacy": 3,
                "inferential_credibility": 3,
                "venue_fit": 3,
                "execution_burden": 3,
            }
        )
    )
    result = await screen_idea(
        session=db_session, idea_card={"research_question": "x"}, provider=fake
    )
    assert result["thresholds"] == {
        "composite": 2.5,
        "novelty": 2,
        "data_adequacy": 2,
        "strict_per_dimension": False,
    }


@pytest.mark.asyncio
async def test_per_dimension_scores_preserved(monkeypatch, db_session):
    """The full `scores` dict from the LLM response (with per-dimension
    score + reason) is preserved verbatim — that's the source of the
    screenings.scores data the orchestrator now surfaces in the batch
    response."""
    monkeypatch.setattr(
        "app.services.paper_generation.roles.scout.settings.scout_screen_strict_per_dimension",
        False,
    )
    fake = _FakeProvider(
        _llm_response(
            {
                "importance": 4,
                "novelty": 3,
                "data_adequacy": 2,
                "inferential_credibility": 5,
                "venue_fit": 3,
                "execution_burden": 4,
            }
        )
    )
    result = await screen_idea(
        session=db_session, idea_card={"research_question": "x"}, provider=fake
    )
    scores = result.get("scores", {})
    assert scores["novelty"]["score"] == 3
    assert scores["data_adequacy"]["score"] == 2
    assert scores["inferential_credibility"]["score"] == 5
