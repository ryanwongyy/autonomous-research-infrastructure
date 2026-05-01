"""Tests that manuscript content is durable across Render redeploys.

Production observation: Render's filesystem is ephemeral. Files
written under ``settings.papers_dir`` get wiped on every redeploy.
The DB row's ``paper_tex_path`` still points at the (now-missing) file
and ``GET /papers/{id}/export?format=tex`` returns 404 even on papers
that completed Packager and passed L1 review.

PR #58 fixes this by adding a ``Paper.manuscript_latex`` TEXT column
that holds the actual content. Drafter writes to this column in Phase
3 alongside the existing title write. The export endpoint and L1
review prefer the DB column over the disk file.

This file locks in:
  * The Paper model has a ``manuscript_latex`` column.
  * Drafter writes to it in Phase 3.
  * L1's ``_load_manuscript_text`` prefers the DB column.
  * The export endpoint serves from the DB column when present.
  * The export endpoint falls back to disk for pre-PR-58 papers.
  * The backfill endpoint exists and requires admin auth.
"""

from __future__ import annotations

import inspect

import pytest
from sqlalchemy import select

# ── Model: column exists ─────────────────────────────────────────────────────


def test_paper_has_manuscript_latex_column():
    from app.models.paper import Paper

    assert hasattr(Paper, "manuscript_latex"), (
        "Paper model must have manuscript_latex column for durable storage."
    )


def test_startup_migration_adds_manuscript_latex():
    """``_ensure_added_columns`` in main.py must include the
    ``manuscript_latex`` ALTER so production Postgres gets the column
    on the next deploy."""
    from app.main import _ensure_added_columns

    src = inspect.getsource(_ensure_added_columns)
    assert "manuscript_latex" in src, (
        "Startup migration must add the manuscript_latex column to "
        "papers via raw SQL — Base.metadata.create_all doesn't ALTER "
        "existing tables."
    )
    assert "ADD COLUMN IF NOT EXISTS" in src, "ALTER must be idempotent (IF NOT EXISTS)."


# ── Drafter persists to the column ───────────────────────────────────────────


def test_drafter_writes_manuscript_latex_to_paper():
    """Source check: compose_manuscript's Phase 3 must set
    paper.manuscript_latex from the LLM-produced text before commit."""
    from app.services.paper_generation.roles.drafter import compose_manuscript

    src = inspect.getsource(compose_manuscript)
    assert "paper.manuscript_latex = manuscript_latex" in src, (
        "Drafter Phase 3 must persist manuscript_latex on the Paper row "
        "so the content survives Render redeploys."
    )


# ── L1 review reads from the column ──────────────────────────────────────────


def test_l1_load_manuscript_text_prefers_db_column():
    """Source check: L1's _load_manuscript_text must check
    paper.manuscript_latex BEFORE attempting the disk file."""
    from app.services.review_pipeline.l1_structural import _load_manuscript_text

    src = inspect.getsource(_load_manuscript_text)

    # Both checks must be present.
    assert "paper.manuscript_latex" in src
    assert "paper_tex_path" in src

    # The actual code-level check (not docstring): `if paper.manuscript_latex:`
    # must come before the `tex_path = paper.paper_tex_path` assignment.
    db_check_pos = src.find("if paper.manuscript_latex")
    file_assign_pos = src.find("tex_path = paper.paper_tex_path")
    assert db_check_pos > 0
    assert file_assign_pos > 0
    assert db_check_pos < file_assign_pos, (
        "L1 must check the DB column BEFORE the disk file, so wiped "
        "files don't cause artifact_missing on papers with the column."
    )


# ── Export endpoint serves from DB ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_returns_db_content_when_column_populated(authed_client, db_session):
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    family = PaperFamily(
        id="F_DURTEST",
        name="Durability test",
        short_name="DT",
        description="for durability tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="apep_durtest",
        title="Durability paper",
        source="ape",
        status="reviewing",
        review_status="awaiting",
        family_id="F_DURTEST",
        funnel_stage="reviewing",
        manuscript_latex="\\documentclass{article}\\title{Durability}\\begin{document}Hello\\end{document}",
        # Path points to a NON-EXISTENT file — the DB column should still
        # serve content. This is the critical case: file wiped by deploy.
        paper_tex_path="/nonexistent/path/manuscript.tex",
    )
    db_session.add(paper)
    await db_session.commit()

    resp = await authed_client.get("/api/v1/papers/apep_durtest/export?format=tex")
    assert resp.status_code == 200, resp.text
    assert "Durability" in resp.text
    assert resp.headers["content-type"].startswith("application/x-tex")


@pytest.mark.asyncio
async def test_export_falls_back_to_disk_when_db_column_empty(authed_client, db_session, tmp_path):
    """For pre-PR-58 papers (manuscript_latex is NULL), export should
    still serve from disk if the file exists."""
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    # Write a real file to a real path.
    tex_file = tmp_path / "old_paper.tex"
    tex_file.write_text("\\documentclass{article}OLD CONTENT")

    family = PaperFamily(
        id="F_LEGACY",
        name="Legacy test",
        short_name="LG",
        description="for legacy tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="apep_legacy",
        title="Legacy paper",
        source="ape",
        status="reviewing",
        review_status="awaiting",
        family_id="F_LEGACY",
        funnel_stage="reviewing",
        # No manuscript_latex — pre-PR-58 paper.
        paper_tex_path=str(tex_file),
    )
    db_session.add(paper)
    await db_session.commit()

    resp = await authed_client.get("/api/v1/papers/apep_legacy/export?format=tex")
    assert resp.status_code == 200
    assert "OLD CONTENT" in resp.text


@pytest.mark.asyncio
async def test_export_404_when_neither_column_nor_disk(authed_client, db_session):
    """If both the DB column and the disk file are missing, return 404
    with a message that explains the situation."""
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    family = PaperFamily(
        id="F_GONE",
        name="Gone test",
        short_name="GN",
        description="for missing-artifact tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="apep_gone",
        title="x",
        source="ape",
        status="reviewing",
        review_status="awaiting",
        family_id="F_GONE",
        funnel_stage="reviewing",
        paper_tex_path="/wiped/by/deploy.tex",  # not real
    )
    db_session.add(paper)
    await db_session.commit()

    resp = await authed_client.get("/api/v1/papers/apep_gone/export?format=tex")
    assert resp.status_code == 404
    assert "redeploy" in resp.json()["detail"].lower()


# ── Backfill endpoint ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backfill_endpoint_copies_disk_to_db(authed_client, db_session, tmp_path):
    """For a pre-PR-58 paper whose disk file still exists, calling the
    backfill endpoint should copy the content into the DB column."""
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    tex_file = tmp_path / "paper.tex"
    tex_file.write_text("\\title{Backfill}")

    db_session.add(
        PaperFamily(
            id="F_BF",
            name="Backfill test",
            short_name="BF",
            description="for backfill tests",
            lock_protocol_type="open",
            active=True,
        )
    )
    db_session.add(
        Paper(
            id="apep_bftest",
            title="Backfill",
            source="ape",
            status="reviewing",
            review_status="awaiting",
            family_id="F_BF",
            funnel_stage="reviewing",
            paper_tex_path=str(tex_file),
        )
    )
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/apep_bftest/backfill-manuscript",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "backfilled"

    # Now the DB column should be populated.
    reloaded = (
        await db_session.execute(select(Paper).where(Paper.id == "apep_bftest"))
    ).scalar_one()
    await db_session.refresh(reloaded)
    assert reloaded.manuscript_latex is not None
    assert "Backfill" in reloaded.manuscript_latex


@pytest.mark.asyncio
async def test_backfill_idempotent_when_already_populated(authed_client, db_session):
    """Already-populated papers return 'already_populated' (no-op)."""
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    db_session.add(
        PaperFamily(
            id="F_BFI",
            name="x",
            short_name="BI",
            description="x",
            lock_protocol_type="open",
            active=True,
        )
    )
    db_session.add(
        Paper(
            id="apep_bfidem",
            title="x",
            source="ape",
            status="reviewing",
            review_status="awaiting",
            family_id="F_BFI",
            funnel_stage="reviewing",
            manuscript_latex="\\title{Already there}",
        )
    )
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/apep_bfidem/backfill-manuscript",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_populated"


@pytest.mark.asyncio
async def test_backfill_404_when_disk_file_missing(authed_client, db_session):
    """When disk file is gone (typical for ephemeral filesystem),
    backfill returns 404 with a clear explanation."""
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    db_session.add(
        PaperFamily(
            id="F_BFG",
            name="x",
            short_name="BG",
            description="x",
            lock_protocol_type="open",
            active=True,
        )
    )
    db_session.add(
        Paper(
            id="apep_bfgone",
            title="x",
            source="ape",
            status="reviewing",
            review_status="awaiting",
            family_id="F_BFG",
            funnel_stage="reviewing",
            paper_tex_path="/wiped/path.tex",
        )
    )
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/apep_bfgone/backfill-manuscript",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 404
    assert "unrecoverable" in resp.json()["detail"].lower()


def test_backfill_endpoint_requires_admin():
    """Source check: the backfill endpoint must declare admin auth."""
    from app.api import papers as papers_module

    src = inspect.getsource(papers_module)

    bf_pos = src.find("backfill-manuscript")
    assert bf_pos > 0
    window = src[max(0, bf_pos - 200) : bf_pos + 300]
    assert "admin_key_required" in window


# ── Module imports clean ─────────────────────────────────────────────────────


def test_paper_module_imports_clean():
    from app.models import paper as paper_module

    assert paper_module.Paper is not None
