"""Shared fixtures for the AI governance research infrastructure test suite."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all models with Base.metadata before create_all
from app.database import Base, get_db

# In-memory SQLite for tests — fast and isolated.
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app with a test database."""
    from app.main import app

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _test_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client(db_engine, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with a valid API key pre-configured."""
    from app.main import app

    monkeypatch.setattr("app.config.settings.ape_api_key", "test-api-key")
    monkeypatch.setattr("app.config.settings.ape_admin_key", "test-admin-key")

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _test_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-api-key"},
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Full pipeline integration fixture ────────────────────────────────────────


@pytest_asyncio.fixture
async def full_pipeline(client, db_engine):
    """Create a realistic entity graph spanning the full pipeline.

    Depends on ``client`` to guarantee the FastAPI override is active
    and the in-memory database already has tables before we write.

    Families:
        F_int_1 -- 5 papers (3 ape, 2 benchmark), ratings, reviews, tournament, etc.
        F_int_2 -- 2 papers (1 ape, 1 benchmark), ratings only.

    Returns a dict with named keys for all created objects.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    db_session = session_factory()
    import json
    from datetime import datetime

    from app.models.autonomy_card import AutonomyCard
    from app.models.correction_record import CorrectionRecord
    from app.models.expert_review import ExpertReview
    from app.models.failure_record import FailureRecord
    from app.models.match import Match
    from app.models.novelty_check import NoveltyCheck
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily
    from app.models.rating import Rating
    from app.models.review import Review
    from app.models.significance_memo import SignificanceMemo
    from app.models.submission_outcome import SubmissionOutcome
    from app.models.tournament_run import TournamentRun

    now = datetime.now(UTC)

    # ── Families ─────────────────────────────────────────────────────────────
    fam1 = PaperFamily(
        id="F_int_1",
        name="Integration Test Family One",
        short_name="IntOne",
        description="Primary integration test family",
        lock_protocol_type="venue-lock",
        active=True,
    )
    fam2 = PaperFamily(
        id="F_int_2",
        name="Integration Test Family Two",
        short_name="IntTwo",
        description="Secondary integration test family",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add_all([fam1, fam2])
    await db_session.flush()

    # ── Papers ───────────────────────────────────────────────────────────────
    # F_int_1: 5 papers (3 ape, 2 benchmark)
    paper_configs_f1 = [
        ("int_p1", "ape", "regulation", "DiD", "published", "candidate", "candidate"),
        ("int_p2", "ape", "regulation", "RDD", "published", "reviewing", "internal"),
        ("int_p3", "ape", "regulation", "IV", "published", "drafting", "internal"),
        ("int_p4", "benchmark", "regulation", "DiD", "published", "public", "public"),
        ("int_p5", "benchmark", "education", "RDD", "killed", "killed", "internal"),
    ]
    papers_f1 = []
    for pid, src, cat, method, status, funnel, release in paper_configs_f1:
        p = Paper(
            id=pid,
            title=f"Paper {pid}",
            source=src,
            category=cat,
            method=method,
            family_id="F_int_1",
            status=status,
            review_status="peer_reviewed",
            funnel_stage=funnel,
            release_status=release,
        )
        db_session.add(p)
        papers_f1.append(p)
    await db_session.flush()

    # F_int_2: 2 papers (1 ape, 1 benchmark)
    papers_f2 = []
    for pid, src in [("int_p6", "ape"), ("int_p7", "benchmark")]:
        p = Paper(
            id=pid,
            title=f"Paper {pid}",
            source=src,
            category="trade",
            family_id="F_int_2",
            status="published",
            review_status="peer_reviewed",
            funnel_stage="analyzing",
            release_status="internal",
        )
        db_session.add(p)
        papers_f2.append(p)
    await db_session.flush()

    all_papers = papers_f1 + papers_f2

    # ── Ratings ──────────────────────────────────────────────────────────────
    # mu / sigma / elo values deliberately varied for predictable sort order.
    rating_specs = [
        # pid,     mu,   sigma, elo,   mp, w, l, d, rank
        ("int_p1", 35.0, 4.0, 1700, 8, 6, 1, 1, 1),
        ("int_p2", 30.0, 5.0, 1600, 6, 4, 1, 1, 2),
        ("int_p3", 28.0, 6.0, 1550, 5, 3, 1, 1, 3),
        ("int_p4", 25.0, 7.0, 1480, 4, 2, 1, 1, 4),
        ("int_p5", 20.0, 8.0, 1400, 3, 1, 1, 1, 5),
        ("int_p6", 32.0, 5.0, 1650, 7, 5, 1, 1, 1),
        ("int_p7", 26.0, 6.5, 1500, 4, 2, 1, 1, 2),
    ]
    ratings = {}
    for pid, mu, sigma, elo, mp, w, l, d, rank in rating_specs:
        fid = "F_int_1" if pid in ("int_p1", "int_p2", "int_p3", "int_p4", "int_p5") else "F_int_2"
        r = Rating(
            paper_id=pid,
            family_id=fid,
            mu=mu,
            sigma=sigma,
            conservative_rating=mu - 3 * sigma,
            elo=elo,
            matches_played=mp,
            wins=w,
            losses=l,
            draws=d,
            rank=rank,
        )
        db_session.add(r)
        ratings[pid] = r
    await db_session.flush()

    # ── Reviews (L1-L3 for F_int_1 papers, 15 total) ────────────────────────
    reviews = []
    verdicts_cycle = ["pass", "pass", "revision_needed"]
    stages = ["l1_structural", "l2_provenance", "l3_method"]
    idx = 0
    for p in papers_f1:
        for stage in stages:
            verdict = verdicts_cycle[idx % len(verdicts_cycle)]
            rev = Review(
                paper_id=p.id,
                family_id="F_int_1",
                stage=stage,
                model_used="gpt-4-turbo",
                verdict=verdict,
                content=f"Review of {p.id} at {stage}: {verdict}",
                iteration=1,
                severity="info" if verdict == "pass" else "warning",
                resolution_status="resolved" if verdict == "pass" else "open",
            )
            db_session.add(rev)
            reviews.append(rev)
            idx += 1
    await db_session.flush()

    # ── TournamentRun + Matches ──────────────────────────────────────────────
    trun = TournamentRun(
        status="completed",
        family_id="F_int_1",
        total_matches=10,
        total_batches=2,
        papers_in_pool=5,
        benchmark_papers=2,
        ai_papers=3,
        completed_at=now,
    )
    db_session.add(trun)
    await db_session.flush()

    matches = []
    match_specs = [
        ("int_p1", "int_p2", "int_p1", "a_wins"),
        ("int_p1", "int_p3", "int_p1", "a_wins"),
        ("int_p1", "int_p4", "int_p1", "a_wins"),
        ("int_p2", "int_p3", "int_p2", "a_wins"),
        ("int_p2", "int_p4", "int_p2", "a_wins"),
        ("int_p3", "int_p4", "int_p3", "a_wins"),
        ("int_p1", "int_p5", "int_p1", "a_wins"),
        ("int_p2", "int_p5", "int_p2", "a_wins"),
        ("int_p3", "int_p5", None, "draw"),
        ("int_p4", "int_p5", "int_p5", "b_wins"),
    ]
    for i, (a, b, winner, result) in enumerate(match_specs):
        m = Match(
            tournament_run_id=trun.id,
            paper_a_id=a,
            paper_b_id=b,
            winner_id=winner,
            judge_model="gpt-4-turbo",
            final_result=result,
            batch_number=1 if i < 5 else 2,
            family_id="F_int_1",
        )
        db_session.add(m)
        matches.append(m)
    await db_session.flush()

    # ── SubmissionOutcomes ───────────────────────────────────────────────────
    outcomes = []
    outcome_specs = [
        ("int_p1", "Nature MI", "accepted", "2025-06-01"),
        ("int_p2", "AJPS", "rejected", "2025-07-01"),
        ("int_p3", "JEP", None, "2025-08-01"),  # pending
    ]
    for pid, venue, decision, date_str in outcome_specs:
        o = SubmissionOutcome(
            paper_id=pid,
            venue_name=venue,
            submitted_date=datetime.fromisoformat(date_str),
            decision=decision,
            decision_date=datetime.fromisoformat(date_str) if decision else None,
        )
        db_session.add(o)
        outcomes.append(o)
    await db_session.flush()

    # ── FailureRecords ───────────────────────────────────────────────────────
    failures = []
    fail_specs = [
        ("int_p2", "F_int_1", "data_error", "high", "l1_structural"),
        ("int_p3", "F_int_1", "hallucination", "critical", "l2_provenance"),
        ("int_p5", "F_int_1", "causal_overreach", "medium", "l3_method"),
    ]
    for pid, fid, ftype, sev, stage in fail_specs:
        f = FailureRecord(
            paper_id=pid,
            family_id=fid,
            failure_type=ftype,
            severity=sev,
            detection_stage=stage,
        )
        db_session.add(f)
        failures.append(f)
    await db_session.flush()

    # ── CorrectionRecords ────────────────────────────────────────────────────
    corrections = []
    corr_specs = [
        ("int_p1", "erratum", "Fixed table 3"),
        ("int_p4", "update", "Updated dataset to v2"),
    ]
    for pid, ctype, desc in corr_specs:
        c = CorrectionRecord(
            paper_id=pid,
            correction_type=ctype,
            description=desc,
            corrected_at=now,
        )
        db_session.add(c)
        corrections.append(c)
    await db_session.flush()

    # ── SignificanceMemo ─────────────────────────────────────────────────────
    sig_memo = SignificanceMemo(
        paper_id="int_p1",
        author="Dr. Smith",
        memo_text="Novel contribution to procurement governance",
        tournament_rank_at_time=1,
        editorial_verdict="submit",
    )
    db_session.add(sig_memo)
    await db_session.flush()

    # ── ExpertReviews ────────────────────────────────────────────────────────
    expert_reviews = []
    for pid, name, score in [("int_p1", "Prof. Jones", 4), ("int_p4", "Dr. Lee", 3)]:
        er = ExpertReview(
            paper_id=pid,
            expert_name=name,
            review_date=now,
            overall_score=score,
            is_pre_submission=True,
        )
        db_session.add(er)
        expert_reviews.append(er)
    await db_session.flush()

    # ── AutonomyCard ─────────────────────────────────────────────────────────
    auto_card = AutonomyCard(
        paper_id="int_p1",
        role_autonomy_json=json.dumps({"scout": "full_auto", "analyst": "supervised"}),
        overall_autonomy_score=0.75,
    )
    db_session.add(auto_card)
    await db_session.flush()

    # ── NoveltyCheck ─────────────────────────────────────────────────────────
    nov_check = NoveltyCheck(
        paper_id="int_p1",
        checked_against_count=50,
        highest_similarity_score=0.35,
        verdict="novel",
        model_used="text-embedding-3-large",
    )
    db_session.add(nov_check)
    await db_session.flush()

    await db_session.commit()
    await db_session.close()

    return {
        "families": [fam1, fam2],
        "papers_f1": papers_f1,
        "papers_f2": papers_f2,
        "all_papers": all_papers,
        "ratings": ratings,
        "reviews": reviews,
        "tournament_run": trun,
        "matches": matches,
        "outcomes": outcomes,
        "failures": failures,
        "corrections": corrections,
        "significance_memo": sig_memo,
        "expert_reviews": expert_reviews,
        "autonomy_card": auto_card,
        "novelty_check": nov_check,
    }
