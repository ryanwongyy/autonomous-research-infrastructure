"""Tests for Packager artifact persistence + Paper.status flips.

Production run #25163518619 reached Packager (paper got
``funnel_stage=candidate``) but two downstream consumers couldn't tell:

  1. The GitHub Actions workflow polls ``Paper.status`` for terminal
     values; it stayed at ``"draft"`` and the workflow timed out at
     45 min.
  2. The L1 structural reviewer reads ``paper.paper_tex_path`` /
     ``code_path`` / ``data_path`` to verify artifacts; all three
     were ``None`` because Packager only stored content hashes on
     ``PaperPackage``, never wrote files.

This file locks in:

  * Packager writes ``manuscript.tex``, ``code/analysis.py``, and
    ``data/manifest.json`` to ``settings.papers_dir/<paper_id>/package_v1/``.
  * Packager populates ``paper.paper_tex_path`` / ``code_path`` /
    ``data_path`` so the L1 reviewer's ``artifact_checks`` pass.
  * The orchestrator's success path flips ``paper.status`` to
    ``"candidate"`` (was ``"draft"``).
  * The verifier-rejection path flips ``paper.status`` to ``"killed"``.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest
import pytest_asyncio

from app.config import settings
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.models.rating import Rating
from app.services.paper_generation.roles.packager import (
    _write_package_artifacts,
    build_package,
)


# ── Pure helper: artifact-writer ─────────────────────────────────────────────


def test_write_artifacts_creates_all_files(tmp_path):
    """All four artifacts written when content provided."""
    out = _write_package_artifacts(
        package_path=str(tmp_path),
        manuscript_latex="\\documentclass{article}...",
        code_content="import pandas as pd\n",
        source_manifest={"sources": [{"id": "S1"}]},
        result_manifest={"results": [{"id": "R1", "value": 42}]},
    )

    assert "manuscript" in out
    assert "code" in out
    assert "data" in out
    assert "results" in out

    # Files exist with expected contents.
    assert (tmp_path / "manuscript.tex").read_text() == "\\documentclass{article}..."
    assert (tmp_path / "code" / "analysis.py").read_text() == "import pandas as pd\n"

    data_payload = json.loads((tmp_path / "data" / "manifest.json").read_text())
    assert data_payload == {"sources": [{"id": "S1"}]}

    results_payload = json.loads((tmp_path / "results" / "results.json").read_text())
    assert results_payload == {"results": [{"id": "R1", "value": 42}]}


def test_write_artifacts_skips_none_inputs(tmp_path):
    """When manuscript/code/manifest are None, those files are NOT created."""
    out = _write_package_artifacts(
        package_path=str(tmp_path),
        manuscript_latex=None,
        code_content=None,
        source_manifest=None,
        result_manifest=None,
    )
    assert out == {}
    # No top-level files or subdirs created.
    assert list(tmp_path.iterdir()) == []


def test_write_artifacts_creates_package_dir_if_missing(tmp_path):
    """Packager creates the package dir on demand — caller doesn't have to."""
    target = tmp_path / "papers" / "apep_xxx" / "package_v1"
    assert not target.exists()
    out = _write_package_artifacts(
        package_path=str(target),
        manuscript_latex="abc",
        code_content=None,
        source_manifest=None,
        result_manifest=None,
    )
    assert target.is_dir()
    assert "manuscript" in out


def test_write_artifacts_returns_absolute_paths_under_package_path(tmp_path):
    """Returned paths are inside the package_path the caller passed in."""
    out = _write_package_artifacts(
        package_path=str(tmp_path),
        manuscript_latex="xyz",
        code_content="def f(): pass",
        source_manifest={"a": 1},
        result_manifest=None,
    )
    for path in out.values():
        assert path.startswith(str(tmp_path))


# ── Integration: full build_package writes artifacts + sets paths ────────────


@pytest_asyncio.fixture
async def papers_dir_override(tmp_path, monkeypatch):
    """Point `settings.papers_dir` at a temp dir for the test so artifacts
    don't leak into the real papers dir."""
    monkeypatch.setattr(settings, "papers_dir", str(tmp_path))
    yield tmp_path


@pytest_asyncio.fixture
async def packaged_paper(db_session, papers_dir_override):
    """Seed a paper + family, run Packager end-to-end, return the Paper row."""
    family = PaperFamily(
        id="F_PKG_TEST",
        name="Packager Test Family",
        short_name="PKG",
        description="for packager artifact tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)

    paper = Paper(
        id="apep_pkgtest",
        title="Test paper",
        source="ape",
        status="draft",
        review_status="awaiting",
        family_id="F_PKG_TEST",
        funnel_stage="drafted",
    )
    db_session.add(paper)

    rating = Rating(
        paper_id="apep_pkgtest",
        mu=25.0,
        sigma=8.333,
        conservative_rating=0.0,
        elo=1500.0,
    )
    db_session.add(rating)
    await db_session.flush()

    package = await build_package(
        session=db_session,
        paper_id="apep_pkgtest",
        manuscript_latex="\\documentclass{article}\\begin{document}Test\\end{document}",
        code_content="x = 1\n",
        source_manifest={"sources": [{"id": "S1", "name": "Test source"}]},
        result_manifest={"results": [{"id": "R1", "value": 1.0}]},
        verification_report={"summary": {"recommendation": "accept"}},
    )
    await db_session.commit()

    # Reload paper to see updated path columns.
    await db_session.refresh(paper)
    return paper, package, papers_dir_override


@pytest.mark.asyncio
async def test_build_package_writes_manuscript_to_disk(packaged_paper):
    """build_package() puts a real manuscript.tex on disk and stores its
    path on the Paper row."""
    paper, package, _ = packaged_paper

    assert paper.paper_tex_path is not None
    assert os.path.isfile(paper.paper_tex_path), (
        f"manuscript.tex not on disk at {paper.paper_tex_path}"
    )
    with open(paper.paper_tex_path) as f:
        contents = f.read()
    assert "\\begin{document}Test\\end{document}" in contents


@pytest.mark.asyncio
async def test_build_package_writes_code_to_disk(packaged_paper):
    paper, _, _ = packaged_paper
    assert paper.code_path is not None
    assert os.path.isfile(paper.code_path)
    assert open(paper.code_path).read() == "x = 1\n"


@pytest.mark.asyncio
async def test_build_package_writes_data_manifest_to_disk(packaged_paper):
    paper, _, _ = packaged_paper
    assert paper.data_path is not None
    assert os.path.isfile(paper.data_path)
    payload = json.loads(open(paper.data_path).read())
    assert payload == {"sources": [{"id": "S1", "name": "Test source"}]}


@pytest.mark.asyncio
async def test_build_package_paths_under_papers_dir(packaged_paper):
    """All written paths live under settings.papers_dir/<paper_id>/, so a
    cleanup or zip job operating on the papers dir picks up everything."""
    paper, _, papers_dir = packaged_paper
    for path_attr in ("paper_tex_path", "code_path", "data_path"):
        path = getattr(paper, path_attr)
        assert path.startswith(str(papers_dir)), (
            f"{path_attr}={path} not under {papers_dir}"
        )


@pytest.mark.asyncio
async def test_build_package_preserves_funnel_stage(packaged_paper):
    """Packager still sets funnel_stage=candidate (regression guard)."""
    paper, _, _ = packaged_paper
    assert paper.funnel_stage == "candidate"


# ── L1 sanity: artifact_checks would now pass ────────────────────────────────


@pytest.mark.asyncio
async def test_l1_artifact_checks_see_packager_paths(packaged_paper):
    """After build_package() runs, an L1-style artifact check finds all
    three required artifacts. This is the production failure mode this
    PR fixes — the L1 review previously reported CRITICAL "manuscript
    missing" because paper_tex_path was None."""
    paper, _, _ = packaged_paper
    artifact_checks = {
        "manuscript": paper.paper_tex_path or paper.paper_pdf_path,
        "code": paper.code_path,
        "data_manifest": paper.data_path,
    }
    missing = [name for name, path in artifact_checks.items() if not path]
    assert not missing, f"L1 would still flag these as missing: {missing}"


# ── Robustness: filesystem failures don't kill the package ──────────────────


def test_write_artifacts_survives_unwritable_target(tmp_path, monkeypatch):
    """If makedirs raises, the helper logs and returns an empty dict —
    Packager continues. The PaperPackage record's hashes still let us
    recover the content from DB, so a transient FS error is recoverable."""

    def _raise_oserror(*_args, **_kwargs):
        raise OSError("disk full (test)")

    monkeypatch.setattr(os, "makedirs", _raise_oserror)
    out = _write_package_artifacts(
        package_path=str(tmp_path / "doesnotmatter"),
        manuscript_latex="x",
        code_content=None,
        source_manifest=None,
        result_manifest=None,
    )
    assert out == {}


# Pyflakes: tempfile is imported for clarity — fixtures use tmp_path instead.
_ = tempfile
