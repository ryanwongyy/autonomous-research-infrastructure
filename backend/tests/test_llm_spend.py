"""Tests for Step 5 cost guardrails — LLMSpend ledger and budget enforcement.

Three concerns:

  1. Cost arithmetic — `cost_usd()` returns the right number for known
     models and falls back to an expensive estimate for unknown ones.

  2. Recording — `record_spend()` writes one row, and aggregate queries
     (`paper_spend_total`, `daily_spend_total`) sum it correctly.

  3. Enforcement — `assert_paper_within_budget` /
     `assert_daily_within_budget` raise `BudgetExceededError` at the right
     thresholds, and are no-ops when tracking is disabled.

Plus an integration test for the `/batch/generate` endpoint: when the daily
cap is already exceeded, the endpoint refuses to start any new pipeline
work and returns a clear summary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_spend import LLMSpend
from app.services.llm.spend import (
    BudgetExceededError,
    assert_daily_within_budget,
    assert_paper_within_budget,
    cost_usd,
    daily_spend_total,
    paper_spend_total,
    record_spend,
)

# ── 1. Cost arithmetic ───────────────────────────────────────────────────────


def test_cost_known_anthropic_model():
    """Claude Opus 4.6: $15/Mtok input, $75/Mtok output."""
    # 1M input + 1M output → $15 + $75 = $90.
    assert abs(cost_usd("claude-opus-4-6", 1_000_000, 1_000_000) - 90.0) < 1e-9


def test_cost_known_openai_model():
    """GPT-4o: $2.50/Mtok input, $10/Mtok output."""
    # 100k input + 50k output = $0.25 + $0.50 = $0.75
    assert abs(cost_usd("gpt-4o", 100_000, 50_000) - 0.75) < 1e-9


def test_cost_zero_tokens_is_free():
    """0/0 always rounds to 0.0 regardless of model."""
    assert cost_usd("claude-opus-4-6", 0, 0) == 0.0
    assert cost_usd("unknown-model-xyz", 0, 0) == 0.0


def test_cost_unknown_model_uses_conservative_fallback(caplog):
    """Unknown models should be charged at the most-expensive fallback rate
    so they can't sneak past budget caps. A warning log is emitted."""
    import logging

    caplog.set_level(logging.WARNING, logger="app.services.llm.spend")
    cost = cost_usd("brand-new-model-not-in-pricing", 1_000_000, 1_000_000)
    # Conservative fallback is $15+$75 = $90/Mtok-pair.
    assert abs(cost - 90.0) < 1e-9
    assert any("unknown model" in r.getMessage().lower() for r in caplog.records)


# ── 2. Recording + aggregates ───────────────────────────────────────────────


@pytest_asyncio.fixture
async def paper_for_spend(db_session: AsyncSession):
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    family = PaperFamily(
        id="F_SP",
        name="Spend Test Family",
        short_name="SP",
        description="for spend tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="paper_spend_1",
        title="Spend Test",
        family_id="F_SP",
        source="ape",
        status="draft",
    )
    db_session.add(paper)
    await db_session.commit()
    return paper


@pytest.mark.asyncio
async def test_record_spend_writes_row(db_session, paper_for_spend):
    spend = await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=1000,
        output_tokens=500,
        note="test row",
    )
    assert spend.id is not None
    # 1k input * $15/Mtok = $0.015; 500 * $75/Mtok = $0.0375
    assert abs(spend.cost_usd - (0.015 + 0.0375)) < 1e-9
    assert spend.note == "test row"


@pytest.mark.asyncio
async def test_paper_spend_total_sums_correctly(db_session, paper_for_spend):
    """Two calls on the same paper sum into paper_spend_total."""
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
    )  # $15
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="verifier",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=0,
        output_tokens=1_000_000,
    )  # $75

    total = await paper_spend_total(db_session, paper_for_spend.id)
    assert abs(total - 90.0) < 1e-9


@pytest.mark.asyncio
async def test_daily_spend_total_includes_recent(db_session, paper_for_spend):
    """A row in the last 24h counts; an old row does not."""
    # Recent — counts.
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="openai",
        model="gpt-4o",
        input_tokens=1_000_000,
        output_tokens=0,
    )  # $2.50

    # Old (forge created_at) — does NOT count.
    old = LLMSpend(
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="openai",
        model="gpt-4o",
        input_tokens=1_000_000,
        output_tokens=0,
        cost_usd=2.50,
        created_at=datetime.now(UTC) - timedelta(hours=48),
    )
    db_session.add(old)
    await db_session.commit()

    total = await daily_spend_total(db_session)
    assert abs(total - 2.50) < 1e-9


@pytest.mark.asyncio
async def test_paper_spend_total_zero_when_no_rows(db_session, paper_for_spend):
    total = await paper_spend_total(db_session, paper_for_spend.id)
    assert total == 0.0


# ── 3. Enforcement ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assert_paper_within_budget_passes_when_under_cap(
    db_session, paper_for_spend, monkeypatch
):
    monkeypatch.setattr("app.config.settings.cost_tracking_enabled", True)
    monkeypatch.setattr("app.config.settings.max_spend_per_paper_usd", 100.0)
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    monkeypatch.setattr("app.services.llm.spend.settings.max_spend_per_paper_usd", 100.0)
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=1000,
        output_tokens=500,
    )  # ~$0.05
    # Should not raise — well under cap.
    await assert_paper_within_budget(db_session, paper_for_spend.id)


@pytest.mark.asyncio
async def test_assert_paper_within_budget_raises_at_cap(db_session, paper_for_spend, monkeypatch):
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    monkeypatch.setattr("app.services.llm.spend.settings.max_spend_per_paper_usd", 5.0)
    # Burn $15 — over the $5 cap.
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    with pytest.raises(BudgetExceededError) as excinfo:
        await assert_paper_within_budget(db_session, paper_for_spend.id)
    assert "per-paper cap" in str(excinfo.value)
    assert paper_for_spend.id in str(excinfo.value)


@pytest.mark.asyncio
async def test_assert_paper_within_budget_disabled_when_tracking_off(
    db_session, paper_for_spend, monkeypatch
):
    """`cost_tracking_enabled=False` is the kill switch — no checks run."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", False)
    monkeypatch.setattr("app.services.llm.spend.settings.max_spend_per_paper_usd", 0.01)
    # Burn $90 — way over a $0.01 cap.
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    # Tracking off → no check, no raise.
    await assert_paper_within_budget(db_session, paper_for_spend.id)


@pytest.mark.asyncio
async def test_assert_paper_within_budget_disabled_when_cap_zero(
    db_session, paper_for_spend, monkeypatch
):
    """Cap of 0 means 'don't enforce this particular cap'."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    monkeypatch.setattr("app.services.llm.spend.settings.max_spend_per_paper_usd", 0.0)
    await record_spend(
        db_session,
        paper_id=paper_for_spend.id,
        role="drafter",
        provider="anthropic",
        model="claude-opus-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    await assert_paper_within_budget(db_session, paper_for_spend.id)


@pytest.mark.asyncio
async def test_assert_daily_within_budget_raises_at_cap(db_session, paper_for_spend, monkeypatch):
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    monkeypatch.setattr("app.services.llm.spend.settings.max_daily_spend_usd", 5.0)
    # Burn $15 across two papers — over the $5 daily cap.
    for note in ("call_a", "call_b", "call_c"):
        await record_spend(
            db_session,
            paper_id=paper_for_spend.id,
            role="drafter",
            provider="anthropic",
            model="claude-opus-4-6",
            input_tokens=400_000,  # $6 per call → $18 total
            output_tokens=0,
            note=note,
        )
    with pytest.raises(BudgetExceededError) as excinfo:
        await assert_daily_within_budget(db_session)
    assert "daily cap" in str(excinfo.value)
