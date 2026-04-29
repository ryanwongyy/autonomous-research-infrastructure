"""Regression tests: long-running role functions split read/LLM/write
into separate short-lived DB sessions.

Background: production run #25135681422 ran for ~11 min and crashed
with::

    asyncpg.InterfaceError:
    cannot call Transaction.commit(): the underlying connection is closed

Even with PR #21's per-stage sessions, a single AsyncSession is held
inside a long stage across the LLM call. If the connection dies during
the LLM call (no DB activity for 5+ min), the final commit on the
held session fails.

The fix: long-running role functions (``generate_analysis_code``,
``execute_analysis``, ``compose_manuscript``, ``verify_manuscript``)
each manage their own short-lived sessions in a read → LLM → write
pattern. No session is ever held across an LLM call.

These tests guard the contract.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles.analyst import (
    execute_analysis,
    generate_analysis_code,
)
from app.services.paper_generation.roles.drafter import compose_manuscript
from app.services.paper_generation.roles.verifier import verify_manuscript


def _has_separated_sessions(fn) -> bool:
    """Check that a role function uses ``async with async_session()`` —
    indicating it manages its own DB lifecycle rather than holding the
    caller's session across the LLM call.
    """
    src = inspect.getsource(fn)
    return src.count("async with async_session()") >= 2 or (
        "async with async_session()" in src and "await provider.complete(" in src
    )


def test_generate_analysis_code_uses_short_lived_sessions():
    src = inspect.getsource(generate_analysis_code)
    # Must open at least 2 short-lived sessions (read phase + write phase)
    assert src.count("async with async_session()") >= 2, (
        "generate_analysis_code must open >= 2 short-lived sessions "
        "(one for reads, one for writes) so the LLM call doesn't hold "
        "a connection across its full duration."
    )


def test_execute_analysis_uses_short_lived_session():
    src = inspect.getsource(execute_analysis)
    # Must open the session AFTER the subprocess runs, not before
    assert "async with async_session()" in src, (
        "execute_analysis must open its DB session AFTER the subprocess "
        "completes, not before — otherwise a long-running subprocess "
        "holds a connection."
    )


def test_compose_manuscript_uses_short_lived_sessions():
    src = inspect.getsource(compose_manuscript)
    assert src.count("async with async_session()") >= 2, (
        "compose_manuscript must split read / LLM-call / write across "
        "separate short-lived sessions."
    )


def test_verify_manuscript_uses_short_lived_sessions():
    src = inspect.getsource(verify_manuscript)
    assert src.count("async with async_session()") >= 2, (
        "verify_manuscript must split read / LLM-call / write across "
        "separate short-lived sessions."
    )


def test_role_functions_take_paper_id_not_session():
    """Each refactored role function takes paper_id (or kwargs); the
    session parameter is optional / kept for back-compat only.
    """
    for fn in (
        generate_analysis_code,
        execute_analysis,
        compose_manuscript,
        verify_manuscript,
    ):
        sig = inspect.signature(fn)
        # Either no `session` parameter, or it has a default value
        # (i.e. it's optional). It must not be required.
        if "session" in sig.parameters:
            assert sig.parameters["session"].default is not inspect.Parameter.empty, (
                f"{fn.__name__} still requires `session` — it should be "
                "optional (back-compat) since the function manages its "
                "own DB sessions internally."
            )
