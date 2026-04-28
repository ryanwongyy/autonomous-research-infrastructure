"""Tests for ``tracked_complete()`` — the wrapper that records LLMSpend
rows around every instrumented LLM call.

Existing call sites in roles (Scout, Designer, Drafter, Verifier, L3, L4,
judge, etc.) call ``provider.complete()`` directly. Migrating them to
``tracked_complete()`` adds one ``LLMSpend`` row per call, keyed by
paper_id + role. This test file covers the wrapper itself; per-role
instrumentation is exercised by their existing tests plus a few targeted
spot-checks.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_spend import LLMSpend
from app.services.llm.provider import LLMProvider
from app.services.llm.spend import tracked_complete


class _FakeProvider(LLMProvider):
    """Test double: returns a fixed string and stashes usage metadata
    exactly the way the real Anthropic / OpenAI / Google providers now do.
    """

    def __init__(
        self,
        *,
        response_text: str = "ok",
        input_tokens: int = 100,
        output_tokens: int = 50,
    ):
        self._text = response_text
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        self.last_usage = {
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "model": model,
        }
        return self._text

    async def complete_with_pdf(
        self,
        pdf_path: str,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:  # pragma: no cover — not exercised here
        return self._text


class _ProviderWithoutUsage(LLMProvider):
    """Pre-instrumentation provider — never sets ``last_usage``. Verifies
    that tracked_complete handles legacy adapters gracefully."""

    async def complete(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        # Deliberately do NOT set self.last_usage.
        return "no-usage"

    async def complete_with_pdf(
        self, pdf_path, messages, model, temperature=0.7, max_tokens=4096
    ):  # pragma: no cover
        return "no-usage"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def paper_for_tracking(db_session: AsyncSession):
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    family = PaperFamily(
        id="F_TRK",
        name="Tracking Test Family",
        short_name="TRK",
        description="for tracked_complete tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="paper_trk_1",
        title="Track Me",
        family_id="F_TRK",
        source="ape",
        status="draft",
    )
    db_session.add(paper)
    await db_session.commit()
    return paper


# ── Behaviour ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tracked_complete_records_one_spend_row(db_session, paper_for_tracking, monkeypatch):
    """Happy path: one call → one LLMSpend row with the right shape."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    provider = _FakeProvider(input_tokens=200_000, output_tokens=10_000)

    text = await tracked_complete(
        provider,
        session=db_session,
        paper_id=paper_for_tracking.id,
        role="drafter",
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": "draft me a paper"}],
        note="test draft",
    )
    assert text == "ok"

    rows = (await db_session.execute(select(LLMSpend))).scalars().all()
    assert len(rows) == 1
    spend = rows[0]
    assert spend.paper_id == paper_for_tracking.id
    assert spend.role == "drafter"
    assert spend.provider == "_fake"  # FakeProvider → "_fake"
    assert spend.model == "claude-opus-4-6"
    assert spend.input_tokens == 200_000
    assert spend.output_tokens == 10_000
    # 200k * $15/Mtok + 10k * $75/Mtok = $3.00 + $0.75 = $3.75
    assert abs(spend.cost_usd - 3.75) < 1e-9
    assert spend.note == "test draft"


@pytest.mark.asyncio
async def test_tracked_complete_returns_text_unchanged(db_session, paper_for_tracking, monkeypatch):
    """The wrapper is transparent: callers get the same text they would
    have gotten from ``provider.complete(...)``."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    provider = _FakeProvider(response_text="the model said this")
    text = await tracked_complete(
        provider,
        session=db_session,
        paper_id=paper_for_tracking.id,
        role="scout",
        model="gpt-4o",
        messages=[{"role": "user", "content": "x"}],
    )
    assert text == "the model said this"


@pytest.mark.asyncio
async def test_tracked_complete_with_no_paper_id(db_session, monkeypatch):
    """Calls outside a paper context (RSI, judge calibration) still record,
    just with paper_id NULL. They count against the daily cap."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    provider = _FakeProvider(input_tokens=1000, output_tokens=500)
    await tracked_complete(
        provider,
        session=db_session,
        paper_id=None,  # no paper
        role="rsi_optimizer",
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": "tune"}],
    )
    rows = (await db_session.execute(select(LLMSpend))).scalars().all()
    assert len(rows) == 1
    assert rows[0].paper_id is None
    assert rows[0].role == "rsi_optimizer"


@pytest.mark.asyncio
async def test_tracked_complete_disabled_when_tracking_off(
    db_session, paper_for_tracking, monkeypatch
):
    """`cost_tracking_enabled=False` is the master kill switch — call
    happens, no row is written."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", False)
    provider = _FakeProvider()
    text = await tracked_complete(
        provider,
        session=db_session,
        paper_id=paper_for_tracking.id,
        role="drafter",
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": "x"}],
    )
    assert text == "ok"
    rows = (await db_session.execute(select(LLMSpend))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_tracked_complete_skips_recording_when_no_usage(
    db_session, paper_for_tracking, monkeypatch
):
    """A legacy provider that never sets ``last_usage`` does not crash the
    wrapper. We get the text back; we do NOT insert a zero-token row."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    provider = _ProviderWithoutUsage()
    text = await tracked_complete(
        provider,
        session=db_session,
        paper_id=paper_for_tracking.id,
        role="some_role",
        model="claude-opus-4-6",
        messages=[{"role": "user", "content": "x"}],
    )
    assert text == "no-usage"
    rows = (await db_session.execute(select(LLMSpend))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_tracked_complete_two_calls_two_rows(db_session, paper_for_tracking, monkeypatch):
    """Aggregate sanity: two calls produce two rows on the same paper."""
    monkeypatch.setattr("app.services.llm.spend.settings.cost_tracking_enabled", True)
    provider = _FakeProvider(input_tokens=1000, output_tokens=500)
    for role in ("scout", "designer"):
        await tracked_complete(
            provider,
            session=db_session,
            paper_id=paper_for_tracking.id,
            role=role,
            model="claude-opus-4-6",
            messages=[{"role": "user", "content": "x"}],
        )
    rows = (await db_session.execute(select(LLMSpend))).scalars().all()
    assert len(rows) == 2
    assert {r.role for r in rows} == {"scout", "designer"}
