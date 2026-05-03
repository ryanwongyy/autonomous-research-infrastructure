"""Tests for PR #74: L3/L4 prefer the durable manuscript_latex
column over the ephemeral disk file.

Production paper apep_4334aa2e (autonomous-loop run 25289671965)
survived L2 (PR #73) but L3 fired ``manuscript_missing``:

  L: l3_method      verdict=fail   "Method review aborted: no manuscript content."
  L: l4_adversarial verdict=fail   "Adversarial review aborted: no manuscript content."

The paper had ``paper.manuscript_latex`` populated (35K of LaTeX,
visible via /export?format=tex) and also had ``paper_tex_path`` set,
but L3/L4's ``_load_manuscript()`` only checked the disk path. On
Render's ephemeral filesystem the file at paper_tex_path was wiped
on a prior redeploy. PR #58 added the durable column for exactly
this case and the export endpoint already prefers it; L3/L4 just
hadn't been updated.

PR #74: prepend the manuscript_latex column to the resolution order
in both L3 and L4. Order is:
  1. paper.manuscript_latex (durable column — PR #58)
  2. paper.paper_tex_path file on disk (legacy)
  3. metadata_json["manuscript_text"] (older path)
  4. paper.abstract (last resort)

This file locks in:
  * Both L3 and L4 check manuscript_latex first
  * The disk-path fallback still exists for pre-PR-58 papers
  * Each module references the production paper that motivated the fix
"""

from __future__ import annotations

import inspect

from app.services.review_pipeline import l3_method, l4_adversarial


def test_l3_load_manuscript_checks_column_first():
    """Source check: the column lookup must come before the disk
    read; the disk-path branch is the fallback."""
    src = inspect.getsource(l3_method._load_manuscript)
    column_pos = src.find("paper.manuscript_latex")
    disk_pos = src.find("paper.paper_tex_path")
    assert column_pos > 0, "L3 _load_manuscript must reference paper.manuscript_latex"
    assert disk_pos > 0, "L3 _load_manuscript must still have the paper_tex_path fallback"
    assert column_pos < disk_pos, (
        "Column read must come BEFORE disk read so durable storage wins over ephemeral storage."
    )


def test_l4_load_manuscript_checks_column_first():
    """Same fix in L4 — both review layers had the same bug and need
    the same patch."""
    src = inspect.getsource(l4_adversarial._load_manuscript)
    column_pos = src.find("paper.manuscript_latex")
    disk_pos = src.find("paper.paper_tex_path")
    assert column_pos > 0, "L4 _load_manuscript must reference paper.manuscript_latex"
    assert disk_pos > 0, "L4 _load_manuscript must still have the paper_tex_path fallback"
    assert column_pos < disk_pos, (
        "Column read must come BEFORE disk read so durable storage wins over ephemeral storage."
    )


def test_l3_returns_column_when_set():
    """Behavior check: when paper.manuscript_latex is non-empty, the
    function returns it without touching the filesystem."""

    class FakePaper:
        manuscript_latex = "DURABLE TEX FROM COLUMN"
        paper_tex_path = "/nonexistent/path.tex"
        metadata_json = None
        abstract = None

    import asyncio

    result = asyncio.run(l3_method._load_manuscript(FakePaper()))
    assert result == "DURABLE TEX FROM COLUMN", (
        "L3 must return the column value when set, even if paper_tex_path is also set."
    )


def test_l4_returns_column_when_set():
    """Behavior check for L4 — same as L3."""

    class FakePaper:
        manuscript_latex = "DURABLE TEX FROM COLUMN"
        paper_tex_path = "/nonexistent/path.tex"
        metadata_json = None
        abstract = None

    import asyncio

    result = asyncio.run(l4_adversarial._load_manuscript(FakePaper()))
    assert result == "DURABLE TEX FROM COLUMN"


def test_l3_falls_back_when_column_empty():
    """When the column is empty/None and the disk path is unreachable,
    the function should NOT crash — it should fall through to the
    abstract or return None."""

    class FakePaper:
        manuscript_latex = None
        paper_tex_path = None
        metadata_json = None
        abstract = "fallback abstract content"

    import asyncio

    result = asyncio.run(l3_method._load_manuscript(FakePaper()))
    assert result == "fallback abstract content"


def test_l3_references_production_paper_in_comment():
    """Future-self trace to the paper that motivated the fix."""
    src = inspect.getsource(l3_method._load_manuscript)
    assert "apep_4334aa2e" in src or "PR #58" in src


def test_modules_import_clean():
    assert l3_method._load_manuscript is not None
    assert l4_adversarial._load_manuscript is not None
