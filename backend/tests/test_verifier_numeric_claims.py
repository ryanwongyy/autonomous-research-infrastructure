"""Tests for numeric / result-object claim verification.

Step 3 made claims with a quoted ``source_span_ref`` mechanically checkable
against the snapshot bytes. This file covers the parallel concern: claims
that reference a *result object* (a number or table cell from the analyst's
output) must be mechanically traceable to that exact result, not just
plausible-looking to an LLM.

The check is implemented in
``app.services.paper_generation.roles.verifier._check_result_object_ref``
and wired into ``_mechanical_verify_claims`` so a fabricated number in
fluent prose can no longer pass — even when there is no quoted source.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_map import ClaimMap
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.paper_generation.roles.verifier import (
    _check_result_object_ref,
    _mechanical_verify_claims,
    _traverse_path,
    _values_match,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def paper_only(db_session: AsyncSession):
    """Bare paper for claims that don't need a snapshot."""
    family = PaperFamily(
        id="F_NUM",
        name="Numeric Claims Test",
        short_name="NUM",
        description="for numeric claim tests",
        lock_protocol_type="empirical_causal",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="paper_num_1",
        title="Numeric Claims Paper",
        family_id="F_NUM",
        source="ape",
        status="draft",
    )
    db_session.add(paper)
    await db_session.commit()
    return paper


SAMPLE_MANIFEST = {
    "result_objects": {
        "regression": {
            "beta_1": {"estimate": 0.42, "se": 0.05, "p_value": 0.001},
            "beta_2": {"estimate": -0.18, "se": 0.07, "p_value": 0.018},
        },
        "summary": {
            "n_observations": 1234,
            "r_squared": 0.67,
        },
        "tables": [
            {"name": "table_1", "rows": [{"id": "row_a", "value": 100}]},
            {"name": "table_2", "rows": [{"id": "row_b", "value": 200}]},
        ],
    }
}


# ── _traverse_path ────────────────────────────────────────────────────────────


def test_traverse_path_dict_keys():
    leaf, ok = _traverse_path(SAMPLE_MANIFEST["result_objects"], "regression.beta_1.estimate")
    assert ok
    assert leaf == 0.42


def test_traverse_path_list_index():
    leaf, ok = _traverse_path(SAMPLE_MANIFEST["result_objects"], "tables.0.name")
    assert ok
    assert leaf == "table_1"


def test_traverse_path_mixed_dict_and_list():
    leaf, ok = _traverse_path(SAMPLE_MANIFEST["result_objects"], "tables.1.rows.0.value")
    assert ok
    assert leaf == 200


def test_traverse_path_missing_key():
    _, ok = _traverse_path(SAMPLE_MANIFEST["result_objects"], "regression.beta_99")
    assert not ok


def test_traverse_path_out_of_range_index():
    _, ok = _traverse_path(SAMPLE_MANIFEST["result_objects"], "tables.5")
    assert not ok


def test_traverse_path_into_scalar():
    """Traversing into a leaf scalar is a miss, not a crash."""
    _, ok = _traverse_path(SAMPLE_MANIFEST["result_objects"], "summary.n_observations.foo")
    assert not ok


# ── _values_match ────────────────────────────────────────────────────────────


def test_values_match_exact_float():
    assert _values_match(0.42, 0.42)


def test_values_match_within_tolerance():
    """Trailing-decimal jitter from float round-trips passes."""
    assert _values_match(0.42, 0.4200000001)


def test_values_match_outside_tolerance_fails():
    assert not _values_match(0.42, 0.43)


def test_values_match_string_to_number_coercion():
    """Common case: claim stores ``"0.42"`` (string), manifest has 0.42 (float)."""
    assert _values_match(0.42, "0.42")
    assert _values_match("0.42", 0.42)


def test_values_match_strings_equal():
    assert _values_match("hello", "hello")
    assert not _values_match("hello", "world")


def test_values_match_bools():
    """Bool comparisons follow Python semantics — ``True == 1`` matches.
    This is acceptable: a ``bool`` claim that the manifest reports as ``1``
    is in practice the same fact, and refusing to match would create false
    positives more often than catching real bugs."""
    assert _values_match(True, True)
    assert _values_match(True, 1)
    assert not _values_match(True, False)


# ── _check_result_object_ref (per-claim helper) ──────────────────────────────


def _claim(ref: dict) -> ClaimMap:
    """Build a ClaimMap with the given result_object_ref. Other fields are
    irrelevant to the helper."""
    return ClaimMap(
        id=1,
        paper_id="p",
        claim_text="A numeric claim.",
        claim_type="empirical",
        result_object_ref=json.dumps(ref),
        verification_status="pending",
    )


def test_ref_path_resolves_pass():
    claim = _claim({"path": "regression.beta_1.estimate"})
    assert _check_result_object_ref(claim, SAMPLE_MANIFEST) is None


def test_ref_path_with_matching_value_pass():
    claim = _claim({"path": "regression.beta_1.estimate", "value": 0.42})
    assert _check_result_object_ref(claim, SAMPLE_MANIFEST) is None


def test_ref_path_with_mismatched_value_fail():
    claim = _claim({"path": "regression.beta_1.estimate", "value": 0.99})
    failure = _check_result_object_ref(claim, SAMPLE_MANIFEST)
    assert failure is not None
    assert "value mismatch" in failure
    assert "0.42" in failure
    assert "0.99" in failure


def test_ref_unresolvable_path_fail():
    claim = _claim({"path": "regression.beta_99"})
    failure = _check_result_object_ref(claim, SAMPLE_MANIFEST)
    assert failure is not None
    assert "does not resolve" in failure


def test_ref_value_only_present_in_manifest_pass():
    """Value appears somewhere in manifest, even without an explicit path."""
    claim = _claim({"value": 1234})  # n_observations
    assert _check_result_object_ref(claim, SAMPLE_MANIFEST) is None


def test_ref_value_only_absent_from_manifest_fail():
    claim = _claim({"value": 99999})
    failure = _check_result_object_ref(claim, SAMPLE_MANIFEST)
    assert failure is not None
    assert "not found" in failure


def test_ref_malformed_json_fail():
    claim = ClaimMap(
        id=2,
        paper_id="p",
        claim_text="...",
        claim_type="empirical",
        result_object_ref="{not valid json",
        verification_status="pending",
    )
    failure = _check_result_object_ref(claim, SAMPLE_MANIFEST)
    assert failure is not None
    assert "not valid JSON" in failure


def test_ref_non_object_json_fail():
    """A JSON array or scalar is not a valid ref."""
    claim = ClaimMap(
        id=3,
        paper_id="p",
        claim_text="...",
        claim_type="empirical",
        result_object_ref=json.dumps([1, 2, 3]),
        verification_status="pending",
    )
    failure = _check_result_object_ref(claim, SAMPLE_MANIFEST)
    assert failure is not None
    assert "must be a JSON object" in failure


def test_ref_empty_object_passes_through():
    """An empty ref has neither path nor value — no mechanical check possible.
    The LLM still inspects."""
    claim = _claim({})
    assert _check_result_object_ref(claim, SAMPLE_MANIFEST) is None


def test_ref_accepts_bare_results_dict():
    """The manifest's results may not be wrapped in ``result_objects``."""
    bare = SAMPLE_MANIFEST["result_objects"]
    claim = _claim({"path": "regression.beta_1.estimate", "value": 0.42})
    assert _check_result_object_ref(claim, bare) is None


# ── _mechanical_verify_claims integration ────────────────────────────────────


@pytest.mark.asyncio
async def test_mechanical_verify_with_result_manifest_catches_fabricated_number(
    db_session, paper_only
):
    """A claim that cites a fabricated regression coefficient is caught."""
    fab = ClaimMap(
        paper_id=paper_only.id,
        claim_text="The treatment effect is 0.99 (highly significant).",
        claim_type="empirical",
        result_object_ref=json.dumps({"path": "regression.beta_1.estimate", "value": 0.99}),
        verification_status="pending",
    )
    db_session.add(fab)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [fab], result_manifest=SAMPLE_MANIFEST)
    assert fab.id in failures
    assert "value mismatch" in failures[fab.id]


@pytest.mark.asyncio
async def test_mechanical_verify_passes_when_number_matches_manifest(db_session, paper_only):
    valid = ClaimMap(
        paper_id=paper_only.id,
        claim_text="The treatment effect is 0.42.",
        claim_type="empirical",
        result_object_ref=json.dumps({"path": "regression.beta_1.estimate", "value": 0.42}),
        verification_status="pending",
    )
    db_session.add(valid)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [valid], result_manifest=SAMPLE_MANIFEST)
    assert failures == {}


@pytest.mark.asyncio
async def test_mechanical_verify_skips_numeric_check_when_no_manifest(db_session, paper_only):
    """Without a manifest, numeric claims fall back to the LLM verifier."""
    claim = ClaimMap(
        paper_id=paper_only.id,
        claim_text="The treatment effect is 0.99.",
        claim_type="empirical",
        result_object_ref=json.dumps({"value": 0.99}),
        verification_status="pending",
    )
    db_session.add(claim)
    await db_session.commit()

    failures = await _mechanical_verify_claims(db_session, [claim], result_manifest=None)
    assert failures == {}  # No manifest → check is skipped, not failed


@pytest.mark.asyncio
async def test_mechanical_verify_handles_mixed_quote_and_numeric_claims(db_session, paper_only):
    """A claim with both a snapshot ref AND a result_object_ref must pass
    BOTH checks. The numeric check is checked first; if it fails we don't
    bother with the snapshot check."""
    # No snapshot fixture here — claim has only result_object_ref. Verifies
    # the numeric path is exercised independently of the snapshot path.
    bad = ClaimMap(
        paper_id=paper_only.id,
        claim_text="Made up.",
        claim_type="empirical",
        result_object_ref=json.dumps({"path": "summary.r_squared", "value": 0.99}),
        verification_status="pending",
    )
    good = ClaimMap(
        paper_id=paper_only.id,
        claim_text="Real.",
        claim_type="empirical",
        result_object_ref=json.dumps({"path": "summary.r_squared", "value": 0.67}),
        verification_status="pending",
    )
    db_session.add_all([bad, good])
    await db_session.commit()

    failures = await _mechanical_verify_claims(
        db_session, [bad, good], result_manifest=SAMPLE_MANIFEST
    )
    assert set(failures.keys()) == {bad.id}
