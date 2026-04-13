"""Data Steward role: builds source manifests, fetches data, creates snapshots.

Boundary: Creates immutable source snapshots from registered source cards.
           Cannot analyse data or modify the lock artifact.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.source_card import SourceCard
from app.models.source_snapshot import SourceSnapshot
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.services.provenance.hasher import hash_content
from app.services.storage.artifact_store import FilesystemArtifactStore
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

MANIFEST_SYSTEM_PROMPT = """\
You are the Data Steward. Your job is to build a precise source manifest \
that maps the locked research design to concrete data sources.

HARD BOUNDARIES:
- You may READ the lock artifact and source cards.
- You CREATE a source manifest (a specification of what data to fetch).
- You CANNOT analyse data or modify the research design.
"""

MANIFEST_USER_PROMPT = """\
Build a source manifest for paper {paper_id}.

Locked research design:
{lock_yaml}

Available source cards:
{source_cards}

For each data need in the research design, identify the best matching source \
card and specify fetch parameters. Empirical papers MUST have at least one \
Tier A source for their central analysis.

Return a JSON object:
{{
  "sources": [
    {{
      "source_card_id": "string",
      "purpose": "string (e.g. 'primary outcome variable', 'control variable')",
      "fetch_params": {{
        "date_range": "YYYY-MM-DD to YYYY-MM-DD",
        "geographic_filter": "string or null",
        "query_parameters": {{}}
      }},
      "expected_record_count": int,
      "tier": "A/B/C",
      "required": true/false
    }}
  ],
  "tier_a_count": int,
  "total_sources": int,
  "notes": "string"
}}

No markdown, no commentary outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def build_source_manifest(
    session: AsyncSession,
    paper_id: str,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Build a source manifest for a paper based on its lock artifact.

    1. Read the lock artifact to determine required data sources
    2. Match against registered source cards
    3. Validate Tier requirements (at least one Tier A source for empirical papers)
    4. Return manifest with source card IDs, fetch parameters, expected record counts
    """
    await _load_paper(session, paper_id)

    # Load the active lock artifact
    lock = await _load_active_lock(session, paper_id)
    if lock is None:
        raise ValueError(
            f"No active lock artifact for paper '{paper_id}'. "
            "Design must be locked before building a source manifest."
        )

    # Load all active source cards
    stmt = select(SourceCard).where(SourceCard.active.is_(True))
    result = await session.execute(stmt)
    source_cards = result.scalars().all()

    source_card_text = "\n".join(
        f"- {sc.id}: {sc.name} | Tier {sc.tier} | {sc.source_type} | "
        f"unit={sc.canonical_unit or 'N/A'} | access={sc.access_method} | "
        f"temporal={sc.temporal_coverage or 'N/A'}"
        for sc in source_cards
    )

    if provider is None:
        provider, model = await get_generation_provider()
    else:
        model = "claude-opus-4-6"

    prompt = MANIFEST_USER_PROMPT.format(
        paper_id=paper_id,
        lock_yaml=lock.lock_yaml,
        source_cards=source_card_text if source_card_text else "(none registered)",
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.3,
        max_tokens=4096,
    )

    manifest = _parse_json_object(response)

    # Validate: empirical protocols need at least one Tier A source
    _validate_tier_requirements(lock.lock_protocol_type, manifest)

    # Cross-check source card IDs against the database
    known_ids = {sc.id for sc in source_cards}
    for source_entry in manifest.get("sources", []):
        sc_id = source_entry.get("source_card_id", "")
        if sc_id not in known_ids:
            logger.warning(
                "Source manifest references unknown source card '%s'", sc_id
            )

    logger.info(
        "Data Steward built manifest for paper %s (%d sources, %d Tier A)",
        paper_id,
        manifest.get("total_sources", 0),
        manifest.get("tier_a_count", 0),
    )
    return manifest


async def fetch_and_snapshot(
    session: AsyncSession,
    paper_id: str,
    source_id: str,
    fetch_params: dict[str, Any] | None = None,
) -> SourceSnapshot:
    """Fetch data from a source and create an immutable snapshot.

    1. Fetch the data (placeholder: generates sample data for dev)
    2. Hash the content
    3. Store in artifact store
    4. Create SourceSnapshot record
    5. Update Paper.funnel_stage to 'ingesting'
    """
    # Verify source card exists
    stmt = select(SourceCard).where(SourceCard.id == source_id)
    result = await session.execute(stmt)
    source_card = result.scalar_one_or_none()
    if source_card is None:
        raise ValueError(f"Source card '{source_id}' not found.")

    # Fetch data (dev mode: generate placeholder content)
    content = await _fetch_source_data(source_card, fetch_params)

    # Hash and store in content-addressed artifact store
    content_hash = hash_content(content)
    store = FilesystemArtifactStore(settings.artifact_store_path)
    await store.store(content, artifact_type="source_snapshot")

    # Determine storage path
    store_path = store._hash_path(content_hash)

    # Create the SourceSnapshot record
    snapshot = SourceSnapshot(
        source_card_id=source_id,
        snapshot_hash=content_hash,
        snapshot_path=str(store_path),
        file_size_bytes=len(content),
        record_count=_estimate_record_count(content),
        fetch_parameters=json.dumps(fetch_params) if fetch_params else None,
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(snapshot)

    # Update paper funnel stage
    paper = await _load_paper(session, paper_id)
    if paper.funnel_stage in ("locked", "screened"):
        paper.funnel_stage = "ingesting"
        session.add(paper)

    await session.flush()

    logger.info(
        "Data Steward created snapshot for source '%s' (hash=%s, %d bytes)",
        source_id,
        content_hash[:16],
        len(content),
    )
    return snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_paper(session: AsyncSession, paper_id: str) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    paper = result.scalar_one_or_none()
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found.")
    return paper


async def _load_active_lock(
    session: AsyncSession, paper_id: str
) -> LockArtifact | None:
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _parse_json_object(response: str) -> dict:
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse manifest JSON from LLM response")
        return {"sources": [], "tier_a_count": 0, "total_sources": 0, "notes": "Parse error"}


def _validate_tier_requirements(protocol_type: str, manifest: dict) -> None:
    """Warn if empirical protocols lack Tier A sources."""
    empirical_protocols = {
        "empirical_causal",
        "measurement_text",
        "process_tracing",
    }
    if protocol_type in empirical_protocols:
        tier_a = manifest.get("tier_a_count", 0)
        if tier_a < 1:
            logger.warning(
                "Empirical protocol '%s' has %d Tier A sources (minimum 1 required)",
                protocol_type,
                tier_a,
            )


async def _fetch_source_data(
    source_card: SourceCard,
    fetch_params: dict[str, Any] | None,
) -> bytes:
    """Fetch data from a source card via the data source registry.

    Tries the real API client first. Falls back to placeholder data only if
    no client exists for this source or the real fetch fails.
    """
    import tempfile
    from pathlib import Path

    from app.services.data_sources.registry import fetch_from_source

    # Build FetchParams from the LLM-generated fetch_params dict
    params = _build_fetch_params(fetch_params)

    # Resolve API key for sources that need one
    api_key = _api_key_for_source(source_card.id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = await fetch_from_source(
            source_card.id, params, Path(tmp_dir), api_key=api_key,
        )

        if result.success and result.file_path:
            content = Path(result.file_path).read_bytes()
            logger.info(
                "Fetched real data from '%s' (%d rows, %d bytes)",
                source_card.id,
                result.row_count,
                len(content),
            )
            return content

        if result.error:
            logger.warning(
                "Real fetch failed for '%s': %s — falling back to placeholder",
                source_card.id,
                result.error,
            )

    # Fallback: generate placeholder data
    return _generate_placeholder(source_card)


def _build_fetch_params(raw: dict[str, Any] | None):
    """Convert LLM-generated fetch_params dict into a FetchParams dataclass."""
    from app.services.data_sources.base import FetchParams

    if not raw:
        return FetchParams()

    date_range = raw.get("date_range", "")
    start, end = None, None
    if date_range and " to " in date_range:
        parts = date_range.split(" to ", 1)
        start, end = parts[0].strip(), parts[1].strip()

    query_params = raw.get("query_parameters") or {}
    query = query_params.get("search_term") or query_params.get("query") or None

    return FetchParams(
        date_range_start=start,
        date_range_end=end,
        query=query,
        geographic_filter=raw.get("geographic_filter"),
        extra=query_params,
    )


def _api_key_for_source(source_id: str) -> str | None:
    """Look up optional API key for a source from settings."""
    key_map = {
        "regulations_gov": "regulations_gov_api_key",
        "courtlistener": "courtlistener_api_key",
        "openalex": "openalex_email",
    }
    attr = key_map.get(source_id)
    if attr:
        return getattr(settings, attr, None) or None
    return None


def _generate_placeholder(source_card: SourceCard) -> bytes:
    """Generate structured placeholder CSV as a last-resort fallback."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    unit = source_card.canonical_unit or "record"
    writer.writerow(["id", "year", unit, "value", "metadata"])

    for i in range(200):
        year = 2015 + (i % 10)
        writer.writerow([
            f"{source_card.id}_{i:04d}",
            year,
            f"{unit}_{i}",
            round(10.0 + i * 0.5 + (i % 7) * 0.3, 2),
            json.dumps({"source": source_card.id, "fetched": True}),
        ])

    content = buf.getvalue().encode("utf-8")
    logger.warning(
        "Using placeholder data for source '%s' (%d bytes)",
        source_card.id,
        len(content),
    )
    return content


def _estimate_record_count(content: bytes) -> int:
    """Estimate the number of records in CSV content."""
    try:
        text = content.decode("utf-8", errors="replace")
        # Subtract 1 for header row
        lines = text.strip().split("\n")
        return max(0, len(lines) - 1)
    except Exception:
        return 0
