"""Tests for /batch/generate error surfacing.

Production cron runs were reporting ``"Generated 2, errors 0"`` while
producing 0 actual papers — both papers died at scout but the response
payload showed no error and the counter incremented as if work happened.
This file verifies the patched payload makes silent failures visible:

  - ``error_message`` and ``stage_errors`` are populated whenever a stage
    raises.
  - The generated counter only increments for ``final_status ==
    "completed"``; killed-at-X counts in its own bucket.
  - The summary string distinguishes generated / reviewed / killed_at_X /
    errors so a cron log readable to a human operator says exactly what
    happened.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.api.batch import (
    _extract_stage_details,
    _extract_stage_errors,
    _primary_error_message,
)


# ── Pure helpers ─────────────────────────────────────────────────────────────


def test_extract_stage_errors_pulls_failed_stages():
    report = {
        "stages": {
            "scout": {
                "status": "failed",
                "error": "AuthenticationError: invalid x-api-key",
            },
            "designer": {"status": "skipped"},
        }
    }
    out = _extract_stage_errors(report)
    assert out == {"scout": "AuthenticationError: invalid x-api-key"}


def test_extract_stage_errors_handles_reason_field():
    """Some stage paths use 'reason' instead of 'error'."""
    report = {"stages": {"scout": {"status": "failed", "reason": "No ideas generated"}}}
    out = _extract_stage_errors(report)
    assert out == {"scout": "No ideas generated"}


def test_extract_stage_errors_empty_report():
    assert _extract_stage_errors({}) == {}
    assert _extract_stage_errors({"stages": None}) == {}
    assert _extract_stage_errors({"stages": {}}) == {}


def test_extract_stage_errors_skips_completed_stages():
    report = {
        "stages": {
            "scout": {"status": "completed"},
            "designer": {"status": "completed"},
        }
    }
    assert _extract_stage_errors(report) == {}


def test_primary_error_prefers_killed_at_stage():
    """When final_status is ``killed_at_designer``, return the designer's
    error, not the scout's (even if scout also failed earlier)."""
    stage_errors = {"designer": "DesignError: bad protocol"}
    msg = _primary_error_message(stage_errors, "killed_at_designer")
    assert msg == "DesignError: bad protocol"


def test_primary_error_falls_back_to_first():
    """When final_status doesn't name a stage we have an error for, return
    the first available."""
    stage_errors = {"scout": "first", "designer": "second"}
    assert _primary_error_message(stage_errors, "unknown") == "first"


def test_primary_error_returns_none_when_no_errors():
    assert _primary_error_message({}, "completed") is None


# ── Endpoint integration ─────────────────────────────────────────────────────


@pytest.fixture
def seeded_family(db_session):
    """Make a single active PaperFamily so /batch/generate has somewhere
    to send work."""
    from app.models.paper_family import PaperFamily

    family = PaperFamily(
        id="F_BTC",
        name="Batch Test Family",
        short_name="BTC",
        description="for batch error tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    return family


@pytest.mark.asyncio
async def test_generate_endpoint_surfaces_killed_at_scout_error(
    client, seeded_family, db_session, monkeypatch
):
    """A pipeline that returns ``killed_at_scout`` produces an entry whose
    ``error_message`` equals the scout's exception text. The summary
    distinguishes ``killed_at_scout`` from real ``generated`` papers.
    """
    await db_session.commit()  # so the seeded family is visible

    async def fake_run_full_pipeline(*, session, family_id, paper_id, **_):
        # Mirror the orchestrator's report shape on a scout failure.
        return {
            "paper_id": paper_id,
            "family_id": family_id,
            "stages": {
                "scout": {
                    "status": "failed",
                    "error": "AuthenticationError: invalid x-api-key",
                    "stage_name": "scout",
                    "duration_sec": 0.5,
                }
            },
            "final_status": "killed_at_scout",
            "total_duration_sec": 1.2,
        }

    monkeypatch.setattr(
        "app.services.paper_generation.orchestrator.run_full_pipeline",
        fake_run_full_pipeline,
    )

    resp = await client.post(
        "/api/v1/batch/generate",
        json={"count": 1, "family_id": "F_BTC"},
    )
    assert resp.status_code == 200
    body = resp.json()

    # Exactly one result, killed at scout, with the underlying error visible.
    assert len(body["results"]) == 1
    gen = body["results"][0]["generation"]
    assert gen["status"] == "killed_at_scout"
    assert gen["error_message"] == "AuthenticationError: invalid x-api-key"
    assert gen["stage_errors"] == {"scout": "AuthenticationError: invalid x-api-key"}

    # Summary shows "Generated 0, ..., killed_at_scout 1" — never the old
    # misleading "Generated 1".
    assert "Generated 0" in body["summary"]
    assert "killed_at_scout 1" in body["summary"]


@pytest.mark.asyncio
async def test_generate_endpoint_counts_completed_separately_from_killed(
    client, seeded_family, db_session, monkeypatch
):
    """Mix of one completed + one killed → summary shows ``Generated 1``
    AND ``killed_at_drafter 1`` (i.e. the counters are independent, not
    folded together)."""
    await db_session.commit()

    call_count = {"i": 0}

    async def fake_run_full_pipeline(*, session, family_id, paper_id, **_):
        call_count["i"] += 1
        if call_count["i"] == 1:
            return {
                "paper_id": paper_id,
                "family_id": family_id,
                "stages": {},
                "final_status": "completed",
                "total_duration_sec": 4.5,
            }
        return {
            "paper_id": paper_id,
            "family_id": family_id,
            "stages": {"drafter": {"status": "failed", "error": "RateLimitError: 429"}},
            "final_status": "killed_at_drafter",
            "total_duration_sec": 8.0,
        }

    # Stub review_pipeline so the completed paper doesn't try a real review.
    async def fake_run_review_pipeline(session, paper_id):
        return {"decision": "pass"}

    monkeypatch.setattr(
        "app.services.paper_generation.orchestrator.run_full_pipeline",
        fake_run_full_pipeline,
    )
    monkeypatch.setattr(
        "app.services.review_pipeline.orchestrator.run_review_pipeline",
        fake_run_review_pipeline,
    )

    resp = await client.post(
        "/api/v1/batch/generate", json={"count": 2, "family_id": "F_BTC"}
    )
    body = resp.json()
    assert "Generated 1" in body["summary"]
    assert "killed_at_drafter 1" in body["summary"]
    assert "reviewed 1" in body["summary"]


@pytest.mark.asyncio
async def test_generate_endpoint_surfaces_uncaught_exception(
    client, seeded_family, db_session, monkeypatch
):
    """When run_full_pipeline raises (rather than returning killed_at_*),
    error_message + error_class are surfaced and ``errors`` is bumped."""
    await db_session.commit()

    async def fake_run_full_pipeline(**_):
        raise RuntimeError("DB connection lost")

    monkeypatch.setattr(
        "app.services.paper_generation.orchestrator.run_full_pipeline",
        fake_run_full_pipeline,
    )

    resp = await client.post(
        "/api/v1/batch/generate", json={"count": 1, "family_id": "F_BTC"}
    )
    body = resp.json()
    gen = body["results"][0]["generation"]
    assert gen["status"] == "error"
    assert gen["error_message"] == "DB connection lost"
    assert gen["error_class"] == "RuntimeError"
    assert "errors 1" in body["summary"]


@pytest.mark.asyncio
async def test_generate_endpoint_completed_paper_has_no_error_message(
    client, seeded_family, db_session, monkeypatch
):
    """A successfully completed paper has ``error_message: null`` and
    empty ``stage_errors``."""
    await db_session.commit()

    async def fake_run_full_pipeline(*, session, family_id, paper_id, **_):
        return {
            "paper_id": paper_id,
            "family_id": family_id,
            "stages": {},
            "final_status": "completed",
            "total_duration_sec": 3.1,
        }

    async def fake_run_review_pipeline(session, paper_id):
        return {"decision": "pass"}

    monkeypatch.setattr(
        "app.services.paper_generation.orchestrator.run_full_pipeline",
        fake_run_full_pipeline,
    )
    monkeypatch.setattr(
        "app.services.review_pipeline.orchestrator.run_review_pipeline",
        fake_run_review_pipeline,
    )

    resp = await client.post(
        "/api/v1/batch/generate", json={"count": 1, "family_id": "F_BTC"}
    )
    body = resp.json()
    gen = body["results"][0]["generation"]
    assert gen["status"] == "completed"
    assert gen["error_message"] is None
    assert gen["stage_errors"] == {}
    assert gen["stage_details"] == {}


# ── _extract_stage_details ───────────────────────────────────────────────────


def test_extract_stage_details_picks_up_screening_results():
    """When Scout fails with `No ideas passed screening`, it attaches a
    `screenings` list to the stage report. The new helper surfaces that
    list verbatim under the stage name so the operator can see scores."""
    report = {
        "stages": {
            "scout": {
                "status": "failed",
                "reason": "No ideas passed screening",
                "duration_sec": 122.2,
                "screenings": [
                    {"question": "Q1", "composite": 3.4, "passed": False},
                    {"question": "Q2", "composite": 3.8, "passed": False},
                    {"question": "Q3", "composite": 2.9, "passed": False},
                ],
            }
        }
    }
    out = _extract_stage_details(report)
    assert "scout" in out
    assert len(out["scout"]["screenings"]) == 3
    # Infra fields (status, duration_sec, reason) are stripped.
    assert "status" not in out["scout"]
    assert "duration_sec" not in out["scout"]
    assert "reason" not in out["scout"]


def test_extract_stage_details_only_failed_stages():
    """A stage with status=completed contributes no details, even if it
    has extra fields like manuscripts or output paths."""
    report = {
        "stages": {
            "scout": {"status": "completed", "idea_card": {"q": "..."}},
            "designer": {
                "status": "failed",
                "reason": "Bad protocol",
                "attempted_fields": ["x", "y"],
            },
        }
    }
    out = _extract_stage_details(report)
    assert set(out.keys()) == {"designer"}
    assert out["designer"]["attempted_fields"] == ["x", "y"]


def test_extract_stage_details_empty_when_only_simple_errors():
    """A stage that failed with only a plain error (no extra fields)
    contributes nothing to stage_details — its message is already in
    stage_errors. Avoids duplicating the same error string in two places."""
    report = {
        "stages": {
            "scout": {"status": "failed", "error": "AuthenticationError"},
        }
    }
    out = _extract_stage_details(report)
    assert out == {}


def test_extract_stage_details_handles_empty_report():
    assert _extract_stage_details({}) == {}
    assert _extract_stage_details({"stages": None}) == {}


@pytest.mark.asyncio
async def test_generate_endpoint_surfaces_scout_screenings(
    client, seeded_family, db_session, monkeypatch
):
    """End-to-end: a Scout failure with screenings results in the
    response payload exposing those scores under stage_details.scout."""
    await db_session.commit()

    async def fake_run_full_pipeline(*, session, family_id, paper_id, **_):
        return {
            "paper_id": paper_id,
            "family_id": family_id,
            "stages": {
                "scout": {
                    "status": "failed",
                    "reason": "No ideas passed screening",
                    "duration_sec": 100.0,
                    "screenings": [
                        {
                            "question": "Does AI procurement reduce cost?",
                            "composite": 3.6,
                            "passed": False,
                        },
                        {
                            "question": "Can audits detect bias?",
                            "composite": 4.1,
                            "passed": False,  # composite OK but novelty failed
                        },
                    ],
                }
            },
            "final_status": "killed_at_scout",
            "total_duration_sec": 100.5,
        }

    monkeypatch.setattr(
        "app.services.paper_generation.orchestrator.run_full_pipeline",
        fake_run_full_pipeline,
    )

    resp = await client.post(
        "/api/v1/batch/generate", json={"count": 1, "family_id": "F_BTC"}
    )
    body = resp.json()
    gen = body["results"][0]["generation"]

    assert gen["status"] == "killed_at_scout"
    assert "scout" in gen["stage_details"]
    screenings = gen["stage_details"]["scout"]["screenings"]
    assert len(screenings) == 2
    assert screenings[0]["composite"] == 3.6
    assert screenings[1]["composite"] == 4.1
    # Infra fields stripped from details.
    assert "status" not in gen["stage_details"]["scout"]
    assert "duration_sec" not in gen["stage_details"]["scout"]


# Pyflakes: imported `Any` is exercised by type annotations in helpers above
# under runtime, but not in this file directly.
_ = Any
