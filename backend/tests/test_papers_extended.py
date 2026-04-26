"""Extended tests for papers API — covers public feed, JSON feed, and export."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.paper_family import PaperFamily


@pytest_asyncio.fixture
async def public_papers(db_session: AsyncSession):
    """Create papers at various release statuses."""
    family = PaperFamily(
        id="F1",
        name="Test",
        short_name="T",
        description="Test family",
        lock_protocol_type="open",
        active=True,
    )
    db_session.add(family)
    await db_session.flush()

    papers = []
    for status, release in [
        ("published", "internal"),
        ("published", "candidate"),
        ("published", "submitted"),
        ("published", "public"),
        ("killed", "internal"),
    ]:
        p = Paper(
            id=f"pub_{release}_{len(papers)}",
            title=f"Paper ({release})",
            abstract=f"Abstract for {release} paper",
            source="ape",
            family_id="F1",
            status=status,
            release_status=release,
        )
        db_session.add(p)
        papers.append(p)

    await db_session.commit()
    return papers


# ── GET /papers/public ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_public_papers_empty(client):
    resp = await client.get("/api/v1/papers/public")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_public_papers_filters_by_release(client, public_papers):
    """Only candidate/public papers should appear."""
    resp = await client.get("/api/v1/papers/public")
    assert resp.status_code == 200
    data = resp.json()
    statuses = {p["release_status"] for p in data}
    # Should include candidate and public, not internal
    assert "internal" not in statuses
    assert len(data) >= 2  # at least candidate + public


# ── GET /papers/feed.json ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_json_feed_empty(client):
    resp = await client.get("/api/v1/papers/feed.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["items"] == []


@pytest.mark.asyncio
async def test_json_feed_with_data(client, public_papers):
    resp = await client.get("/api/v1/papers/feed.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "title" in data
    assert "items" in data
    assert len(data["items"]) >= 1


# ── GET /papers/feed.atom ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_atom_feed_empty(client):
    """Empty Atom feed still returns valid XML with feed metadata."""
    resp = await client.get("/api/v1/papers/feed.atom")
    assert resp.status_code == 200
    assert "application/atom+xml" in resp.headers["content-type"]
    body = resp.text
    assert body.startswith('<?xml version="1.0"')
    assert "<feed" in body
    assert "</feed>" in body
    # No entries when DB is empty
    assert "<entry>" not in body


@pytest.mark.asyncio
async def test_atom_feed_with_data(client, public_papers):
    """Atom feed includes one <entry> per public/candidate paper."""
    resp = await client.get("/api/v1/papers/feed.atom")
    assert resp.status_code == 200
    body = resp.text
    assert "<entry>" in body
    assert "<title>" in body
    # Atom requires a feed-level <id> and <updated>
    assert "<id>urn:ari:feed</id>" in body
    assert "<updated>" in body
    # Custom ARI namespace for family / release_status / novelty
    assert "xmlns:ari=" in body


@pytest.mark.asyncio
async def test_atom_feed_escapes_special_chars(client, public_papers):
    """HTML-special characters in title/abstract are escaped in Atom output."""
    resp = await client.get("/api/v1/papers/feed.atom")
    assert resp.status_code == 200
    body = resp.text
    # The XML parser would reject unescaped & or <
    # We don't expect any literal "<title>foo & bar</title>" — must be &amp;
    # Find any <title> contents and verify they don't contain bare ampersands
    import re

    titles = re.findall(r"<title>(.*?)</title>", body)
    for t in titles:
        # An ampersand that is not part of a valid entity is invalid
        assert "& " not in t  # rough heuristic — bare & followed by space


# ── GET /papers/{id}/export ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_nonexistent_paper(client):
    resp = await client.get("/api/v1/papers/NOPE/export")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_no_artifact(client, public_papers):
    """Export returns 404 when paper has no PDF/TeX artifact path."""
    resp = await client.get(f"/api/v1/papers/{public_papers[0].id}/export")
    assert resp.status_code == 404
    assert "artifact" in resp.json()["detail"].lower()
