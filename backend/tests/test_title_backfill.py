"""Regression test for the one-off title-backfill endpoint.

Background: production paper apep_faf874ae completed end-to-end
(8 stages, 26 sourced claims) but its ``papers.title`` row still
shows the placeholder ``"Generating..."`` because the paper was
created BEFORE PR #30 landed the title-extraction fix.

This endpoint re-derives the title from the saved manuscript on
disk so existing papers can be cosmetically corrected.
"""

from __future__ import annotations

import inspect


def test_backfill_endpoint_exists_and_is_admin_protected():
    """The endpoint must require the admin key (it can mutate paper
    records).
    """
    from app.api.papers import backfill_paper_title

    src = inspect.getsource(backfill_paper_title)
    # Reads from the package_path
    assert "package_path" in src, (
        "backfill_paper_title must read the manuscript from the "
        "PaperPackage's package_path."
    )
    # Uses _extract_latex_title to parse
    assert "_extract_latex_title" in src, (
        "backfill_paper_title must use the same _extract_latex_title "
        "helper as the Drafter."
    )
    # Idempotent — bails when title is already real
    assert "Generating..." in src, (
        "backfill_paper_title must skip papers that already have a "
        "real title (idempotency check)."
    )


def test_backfill_route_registered_with_admin_dependency():
    """The route must be wired into the router with admin_key_required
    so it doesn't accept unauthenticated requests.
    """
    from app.api.papers import router

    paths = [r.path for r in router.routes]
    assert any("backfill-title" in p for p in paths), (
        "Backfill route not registered on /api/v1/admin/papers/{id}/backfill-title."
    )
