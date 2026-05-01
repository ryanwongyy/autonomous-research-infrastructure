"""Tests that the Verifier loads source excerpts and passes them to
the LLM so doctrinal claims can be verified against actual text.

Production paper apep_b4680e6e (autonomous-loop run 25212981303) was
a coherent doctrinal law paper with 25 Tier-A claims sourced from
courtlistener (federal court decisions) and federal_register. L1
PASSED. But the Verifier left 23 of 25 claims at status='pending'
because its prompt only included source IDs and tier metadata —
no actual case text. The LLM correctly refused to assess "Court X
held Y" without reading the underlying decision.

PR #65 fixes this by loading the most recent SourceSnapshot for each
source_card_id cited by the batch's claims and including the content
in the prompt. Best-effort: missing files are noted but don't abort.

This file locks in:
  * The prompt template includes a ``{source_excerpts}`` placeholder
    with explicit guidance to the LLM
  * ``_load_source_excerpts`` reads the most recent snapshot per
    source, truncates to a sane size, and gracefully handles missing
    files
  * Phase 1 of verify_manuscript loads excerpts for the cited sources
"""

from __future__ import annotations

import inspect

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper_family import PaperFamily
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.services.paper_generation.roles import verifier as verifier_mod
from app.services.paper_generation.roles.verifier import (
    VERIFY_USER_PROMPT,
    _load_source_excerpts,
    verify_manuscript,
)
from app.utils import utcnow_naive


# ── Prompt template ─────────────────────────────────────────────────────────


def test_prompt_has_source_excerpts_placeholder():
    """{source_excerpts} must be in the template — otherwise format()
    would raise on the new keyword arg."""
    assert "{source_excerpts}" in VERIFY_USER_PROMPT


def test_prompt_guides_llm_on_excerpt_use():
    """The prompt must tell the LLM HOW to use excerpts — otherwise it
    might still refuse to verify when uncertain."""
    # Source-text-vs-claim grounding cue.
    assert "Source excerpts" in VERIFY_USER_PROMPT
    # Explicit instruction not to refuse on grounds of "haven't read it".
    assert "haven't read the source" in VERIFY_USER_PROMPT
    # Mentions check against excerpt for citation accuracy + scope.
    assert "against the source excerpt" in VERIFY_USER_PROMPT


def test_prompt_explains_status_mapping():
    """Tell the LLM what each citation_accuracy status means relative
    to the excerpt."""
    # All three citation_accuracy statuses must have a clear definition.
    assert 'verified' in VERIFY_USER_PROMPT
    assert 'fabricated' in VERIFY_USER_PROMPT
    assert 'unsupported' in VERIFY_USER_PROMPT
    # The prompt must explicitly differentiate them. Line breaks in the
    # template can split phrases across lines; collapse whitespace so
    # the substring search is wrap-tolerant.
    flat = " ".join(VERIFY_USER_PROMPT.split())
    assert "supports the claim" in flat
    assert "contradicts the claim" in flat
    assert "silent" in flat


# ── verify_manuscript wires source_excerpts through ────────────────────────


def test_verify_manuscript_loads_source_excerpts_in_phase1():
    """Source check: Phase 1 must collect cited source IDs and call
    _load_source_excerpts."""
    src = inspect.getsource(verify_manuscript)
    assert "_load_source_excerpts" in src
    assert "cited_source_ids" in src
    # The set comprehension extracts source_card_id from claims.
    assert "c.source_card_id for c in claims" in src


def test_verify_manuscript_passes_source_excerpts_to_format():
    """The format() call must include source_excerpts as a kwarg."""
    src = inspect.getsource(verify_manuscript)
    assert "source_excerpts=source_excerpts" in src


# ── _load_source_excerpts behavior ─────────────────────────────────────────


@pytest_asyncio.fixture
async def seeded_sources(db_session: AsyncSession, tmp_path):
    """Seed two SourceCard rows + one SourceSnapshot file each."""
    db_session.add(
        SourceCard(
            id="SC_courtlistener",
            name="CourtListener",
            tier="A",
            source_type="document",
            access_method="api",
            claim_permissions="[]",
            claim_prohibitions="[]",
            required_corroboration="[]",
            active=True,
        )
    )
    db_session.add(
        SourceCard(
            id="SC_federal_register",
            name="Federal Register",
            tier="A",
            source_type="document",
            access_method="api",
            claim_permissions="[]",
            claim_prohibitions="[]",
            required_corroboration="[]",
            active=True,
        )
    )
    await db_session.flush()

    # Real snapshot file with actual content.
    f1 = tmp_path / "courtlistener.txt"
    f1.write_text(
        "Court held that algorithmic systems used in employment "
        "decisions must comply with disparate-impact analysis under "
        "Title VII. Plaintiffs may challenge unified algorithmic "
        "selection devices without disaggregation."
    )

    # Real snapshot file with different content.
    f2 = tmp_path / "federal_register.txt"
    f2.write_text(
        "29 CFR § 1607.4(d) — Adverse impact and the four-fifths "
        "rule. A selection rate for any race, sex, or ethnic group "
        "which is less than four-fifths of the rate for the group "
        "with the highest rate will generally be regarded as evidence "
        "of adverse impact."
    )

    db_session.add(
        SourceSnapshot(
            source_card_id="SC_courtlistener",
            snapshot_hash="abc123",
            snapshot_path=str(f1),
            file_size_bytes=f1.stat().st_size,
            fetched_at=utcnow_naive(),
        )
    )
    db_session.add(
        SourceSnapshot(
            source_card_id="SC_federal_register",
            snapshot_hash="def456",
            snapshot_path=str(f2),
            file_size_bytes=f2.stat().st_size,
            fetched_at=utcnow_naive(),
        )
    )
    await db_session.commit()
    yield


@pytest.mark.asyncio
async def test_load_excerpts_returns_actual_content(
    db_session, seeded_sources
):
    """When snapshots exist on disk, the excerpt string must contain
    the real content the Verifier needs."""
    text = await _load_source_excerpts(
        db_session, {"SC_courtlistener", "SC_federal_register"}
    )
    assert "SC_courtlistener" in text
    assert "SC_federal_register" in text
    # Real content from the seeded files.
    assert "disparate-impact" in text
    assert "four-fifths" in text


@pytest.mark.asyncio
async def test_load_excerpts_truncates_long_content(
    db_session, tmp_path
):
    """Long snapshots truncate at max_chars_per_source so the prompt
    stays bounded."""
    # Seed a SourceCard + a snapshot pointing at a 10K-char file.
    db_session.add(
        SourceCard(
            id="SC_big",
            name="Big",
            tier="A",
            source_type="document",
            access_method="manual",
            claim_permissions="[]",
            claim_prohibitions="[]",
            required_corroboration="[]",
            active=True,
        )
    )
    big = tmp_path / "big.txt"
    big.write_text("X" * 10000)
    db_session.add(
        SourceSnapshot(
            source_card_id="SC_big",
            snapshot_hash="big",
            snapshot_path=str(big),
            file_size_bytes=10000,
            fetched_at=utcnow_naive(),
        )
    )
    await db_session.commit()

    text = await _load_source_excerpts(db_session, {"SC_big"}, max_chars_per_source=500)
    # Excerpt should be truncated to 500 chars + a marker.
    assert text.count("X") == 500
    assert "truncated" in text


@pytest.mark.asyncio
async def test_load_excerpts_handles_missing_file(db_session, tmp_path):
    """If the snapshot file was wiped (Render's ephemeral fs after
    redeploy), don't crash — note it and move on."""
    db_session.add(
        SourceCard(
            id="SC_gone",
            name="Gone",
            tier="A",
            source_type="document",
            access_method="manual",
            claim_permissions="[]",
            claim_prohibitions="[]",
            required_corroboration="[]",
            active=True,
        )
    )
    db_session.add(
        SourceSnapshot(
            source_card_id="SC_gone",
            snapshot_hash="missing",
            # Path that doesn't exist:
            snapshot_path=str(tmp_path / "nonexistent.txt"),
            file_size_bytes=999,
            fetched_at=utcnow_naive(),
        )
    )
    await db_session.commit()

    text = await _load_source_excerpts(db_session, {"SC_gone"})
    # Should mention the source ID + a missing-file note.
    assert "SC_gone" in text
    assert "missing on disk" in text or "wiped" in text


@pytest.mark.asyncio
async def test_load_excerpts_no_sources_cited(db_session):
    """When the batch's claims cite no sources, return a clear note."""
    text = await _load_source_excerpts(db_session, set())
    assert "no sources cited" in text.lower()


@pytest.mark.asyncio
async def test_load_excerpts_no_snapshots_available(db_session):
    """SourceCards exist but no snapshots have been fetched yet."""
    text = await _load_source_excerpts(db_session, {"SC_unknown"})
    assert "no source snapshots" in text.lower()


@pytest.mark.asyncio
async def test_load_excerpts_uses_most_recent_snapshot(
    db_session, tmp_path
):
    """When a source has multiple snapshots, the latest fetched_at
    wins — older ones are stale."""
    from datetime import timedelta

    db_session.add(
        SourceCard(
            id="SC_history",
            name="History",
            tier="A",
            source_type="document",
            access_method="manual",
            claim_permissions="[]",
            claim_prohibitions="[]",
            required_corroboration="[]",
            active=True,
        )
    )
    old_file = tmp_path / "old.txt"
    old_file.write_text("OLD CONTENT — outdated")
    new_file = tmp_path / "new.txt"
    new_file.write_text("NEW CONTENT — most recent")

    older = utcnow_naive() - timedelta(days=10)
    newer = utcnow_naive()

    db_session.add(
        SourceSnapshot(
            source_card_id="SC_history",
            snapshot_hash="old",
            snapshot_path=str(old_file),
            file_size_bytes=old_file.stat().st_size,
            fetched_at=older,
        )
    )
    db_session.add(
        SourceSnapshot(
            source_card_id="SC_history",
            snapshot_hash="new",
            snapshot_path=str(new_file),
            file_size_bytes=new_file.stat().st_size,
            fetched_at=newer,
        )
    )
    await db_session.commit()

    text = await _load_source_excerpts(db_session, {"SC_history"})
    assert "NEW CONTENT" in text
    assert "OLD CONTENT" not in text


# ── Module imports clean ────────────────────────────────────────────────────


def test_module_imports_clean():
    assert verifier_mod.verify_manuscript is not None
    assert verifier_mod._load_source_excerpts is not None


# Pyflakes
_ = PaperFamily
