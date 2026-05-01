"""Tests that PaperResponse exposes the diagnostic fields callers need.

Production observation: paper apep_cf013012 was killed at the Analyst
stage (PR #48's status flip working — paper.status='killed' set
within 3 min). But the API response showed:

    "status": "killed",
    "review_status": "skipped",
    "error_message": null,
    "last_heartbeat_stage": "analyst"

The orchestrator's ``_set_killed_at_stage`` had written
``kill_reason="killed_at_analyst: <error_text>"`` to the DB row, but
the schema didn't expose ``kill_reason``. Operators see status='killed'
with no diagnostic.

PR #59 surfaces ``kill_reason`` plus the path columns added in PR #44
(``paper_tex_path``, ``code_path``, ``data_path``).
"""

from __future__ import annotations

from app.schemas.paper import PaperResponse, PaperWithRating


def test_paper_response_exposes_kill_reason():
    """PR #59: ``kill_reason`` must be in PaperResponse so operators
    can see WHY a paper was killed without DB access."""
    assert "kill_reason" in PaperResponse.model_fields
    assert "kill_reason" in PaperWithRating.model_fields


def test_paper_response_exposes_artifact_paths():
    """PR #59: PR #44 added the path columns; expose them so operators
    can see whether artifacts were written even after a Render redeploy
    wiped the on-disk file."""
    for field in ("paper_tex_path", "code_path", "data_path"):
        assert field in PaperResponse.model_fields, (
            f"{field} should be in PaperResponse"
        )
        assert field in PaperWithRating.model_fields


def test_kill_reason_is_optional():
    """Most papers won't have a kill_reason — only ones that hit a
    stage failure or verifier rejection. Field must accept None."""
    field = PaperResponse.model_fields["kill_reason"]
    # Pydantic v2: required is False if a default is set.
    assert field.is_required() is False or field.default is None


def test_path_fields_are_optional():
    for name in ("paper_tex_path", "code_path", "data_path", "kill_reason"):
        field = PaperResponse.model_fields[name]
        assert field.is_required() is False or field.default is None


def test_existing_diagnostic_fields_still_present():
    """Regression guard: don't accidentally drop the fields PR #36/37
    added (funnel_stage, error_message, last_heartbeat_*)."""
    for name in (
        "funnel_stage",
        "error_message",
        "last_heartbeat_at",
        "last_heartbeat_stage",
    ):
        assert name in PaperResponse.model_fields
