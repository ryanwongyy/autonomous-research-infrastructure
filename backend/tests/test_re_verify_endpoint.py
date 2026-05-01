"""Tests for the re-verify endpoint that runs Verifier on pending claims.

Empirical observation: Verifier LLM cherry-picks which claims to verify
(documented in PRs #50, #52, #53). Most papers end with ~70% of claims
at ``verification_status='pending'``. PR #54 made partial coverage
acceptable but didn't add a way to incrementally fill in the gaps.

PR #56 (this file's subject) adds POST /api/v1/admin/papers/{id}/re-verify
that runs the Verifier on pending claims only. Repeated calls approach
100% coverage.

This file locks in:

  * verify_manuscript accepts a ``status_filter`` parameter and the
    Phase 1 SELECT applies it.
  * The endpoint exists, requires admin auth, and returns the
    before/after pending count.
  * Calling it on a paper with no pending claims is a no-op.
  * 404 for unknown paper.
"""

from __future__ import annotations

import inspect

import pytest

from app.services.paper_generation.roles import verifier as verifier_mod
from app.services.paper_generation.roles.verifier import verify_manuscript


# ── verify_manuscript supports status_filter ─────────────────────────────────


def test_verify_manuscript_signature_accepts_status_filter():
    """The Verifier function must accept an optional status_filter
    parameter so callers can request 'pending'-only re-verification."""
    sig = inspect.signature(verify_manuscript)
    params = sig.parameters
    assert "status_filter" in params, (
        "verify_manuscript must accept a status_filter parameter."
    )
    # Default should be None (= verify all claims, current behavior).
    assert params["status_filter"].default is None


def test_verify_manuscript_phase1_applies_status_filter():
    """Source check: the SELECT in Phase 1 must apply the filter when
    status_filter is non-None. Otherwise the LLM gets every claim
    regardless of intent."""
    src = inspect.getsource(verify_manuscript)
    # Look for "if status_filter is not None" guard followed by a
    # .where(... verification_status ...) call.
    assert "if status_filter is not None" in src, (
        "verify_manuscript must guard the filter so default behavior "
        "is unchanged."
    )
    assert "ClaimMap.verification_status == status_filter" in src, (
        "Phase 1 must filter ClaimMap.verification_status when status_filter "
        "is provided."
    )


def test_verify_manuscript_default_includes_all_claims():
    """Backward compat: when status_filter is None (the default), the
    Phase 1 SELECT must NOT filter on verification_status."""
    src = inspect.getsource(verify_manuscript)
    # The base statement should still be select(ClaimMap).where(paper_id...).
    # Find the assembly: stmt = select(ClaimMap).where(ClaimMap.paper_id ==
    # paper_id), then optionally add .where(...). The original "where" must
    # be present and must come before the conditional .where.
    paper_filter_pos = src.find("ClaimMap.paper_id == paper_id")
    status_filter_pos = src.find("ClaimMap.verification_status == status_filter")
    assert paper_filter_pos > 0
    assert status_filter_pos > 0
    assert paper_filter_pos < status_filter_pos, (
        "paper_id filter must precede the optional status_filter."
    )


# ── Endpoint exists with admin auth ──────────────────────────────────────────


def test_endpoint_is_registered():
    """The endpoint POST /admin/papers/{id}/re-verify must be registered
    on the papers router."""
    from app.api import papers as papers_module

    routes = [
        r for r in papers_module.router.routes
        if hasattr(r, "path") and "re-verify" in r.path
    ]
    assert routes, "POST /admin/papers/{id}/re-verify must be registered."
    # Must be a POST.
    methods = set()
    for r in routes:
        if hasattr(r, "methods"):
            methods.update(r.methods)
    assert "POST" in methods


def test_endpoint_requires_admin_auth():
    """Source check: the endpoint must use admin_key_required."""
    from app.api import papers as papers_module
    src = inspect.getsource(papers_module)

    # Find the re-verify endpoint definition and look for admin auth.
    re_verify_pos = src.find("re-verify")
    assert re_verify_pos > 0
    # Look 200 chars before for the dependencies declaration.
    window = src[max(0, re_verify_pos - 200):re_verify_pos + 500]
    assert "admin_key_required" in window, (
        "Re-verify endpoint must declare dependencies=[Depends(admin_key_required)]."
    )


# ── Endpoint behavior: no pending = no-op, unknown paper = 404 ──────────────


@pytest.mark.asyncio
async def test_endpoint_returns_404_for_unknown_paper(authed_client):
    resp = await authed_client.post(
        "/api/v1/admin/papers/apep_doesnotexist/re-verify",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_handles_paper_with_no_pending_claims(
    authed_client, db_session
):
    """When the paper has zero pending claims, the endpoint returns
    immediately with before=after=0 and a no-op message."""
    from app.models.paper import Paper
    from app.models.paper_family import PaperFamily

    family = PaperFamily(
        id="F_RV_TEST",
        name="Re-verify test family",
        short_name="RV",
        description="for re-verify endpoint tests",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    paper = Paper(
        id="apep_rvtest",
        title="Test",
        source="ape",
        status="reviewing",
        review_status="awaiting",
        family_id="F_RV_TEST",
        funnel_stage="reviewing",
    )
    db_session.add(paper)
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/admin/papers/apep_rvtest/re-verify",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["before"]["pending"] == 0
    assert body["after"]["pending"] == 0
    # No-op message present.
    assert "message" in body
    assert "no pending" in body["message"].lower()


@pytest.mark.asyncio
async def test_endpoint_rejects_unauth_request_when_admin_key_set(
    db_engine, monkeypatch
):
    """When ``ape_admin_key`` IS configured, a request without the
    correct ``X-API-Key`` header returns 403. (When the admin key is
    blank the dependency falls through to api_key_required, which is
    tested elsewhere.)"""
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database import get_db
    from app.main import app

    monkeypatch.setattr("app.config.settings.ape_admin_key", "secret-admin-key")

    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _test_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _test_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/admin/papers/apep_x/re-verify")
            # No X-API-Key header → admin_key_required returns 403.
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


# ── Module imports clean ─────────────────────────────────────────────────────


def test_module_imports_clean():
    """Sanity: papers module loads without errors after the new endpoint."""
    from app.api import papers as papers_module
    assert papers_module.router is not None


def test_verifier_module_imports_clean():
    """Sanity: verifier module loads without errors after status_filter
    parameter addition."""
    assert verifier_mod.verify_manuscript is not None
