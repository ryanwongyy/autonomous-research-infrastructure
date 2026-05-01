"""Regression test for per-stage timeout contract.

Production paper apep_32868ba9 (autonomous-loop run 25167747205)
heart-beat from Designer at 13:22:51, then went silent for 43 minutes
until the workflow's poll loop timed out at 14:06. No exception was
raised — the stage just hung. Without a wall-clock timeout, the
backend held the pipeline in a half-completed state until something
upstream killed the request.

This test locks in:

  * ``_STAGE_TIMEOUT_SEC`` exists with sensible (single-digit-minutes
    to ~15 min) bounds on each stage.
  * ``_DEFAULT_STAGE_TIMEOUT_SEC`` exists for unlisted stages.
  * Both wrapper helpers use ``asyncio.timeout(...)`` to enforce them.
  * On TimeoutError the wrapper returns a dict (never raises) with
    ``status="failed"`` and ``wrapper_timeout=True`` so external
    observers can distinguish a hang-kill from any other failure.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation import orchestrator


def test_stage_timeout_constants_exist():
    """The dict + default must both exist."""
    assert hasattr(orchestrator, "_STAGE_TIMEOUT_SEC")
    assert isinstance(orchestrator._STAGE_TIMEOUT_SEC, dict)
    assert hasattr(orchestrator, "_DEFAULT_STAGE_TIMEOUT_SEC")
    assert isinstance(orchestrator._DEFAULT_STAGE_TIMEOUT_SEC, int)
    assert orchestrator._DEFAULT_STAGE_TIMEOUT_SEC > 0


def test_every_known_stage_has_a_timeout():
    """Each pipeline stage that appears in run_full_pipeline has an
    entry in the timeout map. Missing entries silently fall through
    to the default — fine for safety, but new stages should opt in
    explicitly so we notice them in code review."""
    expected = {
        "scout",
        "designer",
        "data_steward",
        "analyst",
        "drafter",
        "collegial_review",
        "verifier",
        "packager",
    }
    actual = set(orchestrator._STAGE_TIMEOUT_SEC.keys())
    missing = expected - actual
    assert not missing, f"stages without explicit timeout: {missing}"


def test_timeouts_are_within_sensible_bounds():
    """Each value is in the [60, 1800] range. <60s would race with
    cold starts; >1800s loses the safety net the cap is supposed to
    provide."""
    for stage, timeout in orchestrator._STAGE_TIMEOUT_SEC.items():
        assert 60 <= timeout <= 1800, (
            f"stage {stage!r} has unreasonable timeout {timeout}s — "
            f"expected 60..1800."
        )


def test_packager_timeout_is_short_because_packager_is_pure_db():
    """Packager is filesystem + DB; no LLM. It should take <1s in
    normal operation. Production paper apep_dd9fc939 hung 19 min in
    Packager (an asyncpg pool issue) — the cap must be small enough
    that a hang there is detected fast."""
    assert orchestrator._STAGE_TIMEOUT_SEC["packager"] <= 120, (
        "Packager is DB-only; timeout > 120s defeats the early-detection "
        "purpose of having a per-stage timeout at all."
    )


def test_wrappers_use_asyncio_timeout():
    """Both stage-running helpers must wrap their body in
    ``asyncio.timeout(timeout_sec)``."""
    short_src = inspect.getsource(orchestrator._run_stage_with_session)
    assert "asyncio.timeout(" in short_src, (
        "_run_stage_with_session must enforce a per-stage timeout via "
        "asyncio.timeout(...)."
    )
    long_src = inspect.getsource(orchestrator._run_stage_no_outer_session)
    assert "asyncio.timeout(" in long_src, (
        "_run_stage_no_outer_session must enforce a per-stage timeout."
    )


def test_wrappers_handle_timeout_error_without_raising():
    """When the timeout fires, both wrappers must return a dict
    rather than letting TimeoutError propagate. Caller (the orchestrator)
    expects every wrapper call to return — `wrappers never raise` is
    the contract from PR #42 / test_wrappers_never_raise.py."""
    short_src = inspect.getsource(orchestrator._run_stage_with_session)
    long_src = inspect.getsource(orchestrator._run_stage_no_outer_session)
    for label, src in (("_run_stage_with_session", short_src),
                       ("_run_stage_no_outer_session", long_src)):
        assert "except TimeoutError" in src or "except (TimeoutError" in src, (
            f"{label} must catch TimeoutError. Without the catch, a hung "
            f"stage propagates as an uncaught exception and the next "
            f"stage's wrapper isn't called."
        )
        assert 'wrapper_timeout' in src, (
            f"{label} must mark its TimeoutError-failure dict with "
            f"wrapper_timeout=True so external observers can distinguish "
            f"a hang-kill from a regular stage failure."
        )
        assert '"status": "failed"' in src or "'status': 'failed'" in src, (
            f"{label} must return status='failed' on timeout."
        )


def test_designer_timeout_covers_known_failure_horizon():
    """Production paper apep_32868ba9's Designer hung 43 min before
    the workflow timed out. The timeout for Designer must be well
    below 43 min so we never see that wall-clock again."""
    designer_timeout = orchestrator._STAGE_TIMEOUT_SEC["designer"]
    assert designer_timeout < 1800, (
        f"Designer timeout {designer_timeout}s would still let a hang "
        f"persist for {designer_timeout / 60:.1f} min — production saw "
        f"43 min hangs so this needs to be aggressively short."
    )
