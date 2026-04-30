"""Regression test: collegial review max_rounds defaults conservatively
to fit Render's free-tier HTTP request budget.

Background: production run #25145137906 streamed for 14.7 min then was
cut off — Render's free-tier hard request limit is ~15 min. Collegial
review with 3 colleagues × 5 max rounds × ~30s/colleague = up to 7.5
min of just collegial-review time, leaving no headroom for the other
6 stages.

Cap default at 2 rounds so the full pipeline (Scout + Designer +
Data Steward + Analyst + Drafter + Collegial + Verifier + Packager)
typically completes in ~12 min — comfortably under the 15-min limit.
Operators wanting deeper revision can pass max_rounds= explicitly
once we move to a fire-and-poll job pattern.
"""

from __future__ import annotations

from app.services.collegial.review_loop import DEFAULT_MAX_ROUNDS


def test_collegial_default_max_rounds_fits_render_budget():
    """Default must be small enough that a typical run completes
    inside Render's ~15-min HTTP request limit.
    """
    assert DEFAULT_MAX_ROUNDS <= 3, (
        f"DEFAULT_MAX_ROUNDS = {DEFAULT_MAX_ROUNDS} is too large for "
        f"Render's free-tier HTTP limit. With 3 colleagues × ~30s per "
        f"round, more than 3 rounds risks running the full pipeline "
        f"past the 15-min cap (production run #25145137906 hit this). "
        f"Cap at 2 by default; raise via the explicit max_rounds kwarg."
    )
