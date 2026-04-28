"""Base class for data source clients.

Each data source (Federal Register, EDGAR, etc.) implements this interface.
The fetch() method retrieves real data and writes it to local files.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def make_http_proof(
    *,
    request_url: str,
    response_status: int,
    response_body: bytes,
    fetched_via: str,
) -> dict:
    """Build a Step-2 provenance proof dict for a real HTTP fetch.

    `response_body` should be the raw bytes returned by the upstream API
    (before any normalisation into CSV / JSON-flat). Hashing the raw body
    lets us detect content drift independently of how we serialise it
    locally.
    """
    return {
        "method": "http",
        "request_url": request_url,
        "response_status": response_status,
        "response_hash": hashlib.sha256(response_body).hexdigest(),
        "fetched_at": datetime.now(UTC).isoformat(),
        "fetched_via": fetched_via,
    }


@dataclass
class FetchParams:
    """Parameters controlling what data to fetch from a source."""

    date_range_start: str | None = None  # ISO 8601 date
    date_range_end: str | None = None
    query: str | None = None  # Free-text search query
    geographic_filter: str | None = None  # Country/jurisdiction code
    max_records: int = 1000  # Safety cap
    extra: dict = field(default_factory=dict)  # Source-specific params


@dataclass
class FetchResult:
    """Result of a single source fetch operation."""

    success: bool
    file_path: str | None = None  # Path to the written data file
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    description: str = ""
    error: str | None = None

    # ── Provenance proof (Step 2) ──────────────────────────────────────
    # Sources that perform real HTTP fetches populate `proof` with a dict
    # describing how the response was obtained. The data_steward role
    # writes this dict to SourceSnapshot.provenance_proof_json, and the L2
    # Provenance review rejects claims tied to snapshots whose proof is
    # missing or whose method is anything other than "http" / "vcr".
    #
    # Expected shape:
    #   {
    #     "method": "http",
    #     "request_url": "https://...",
    #     "response_status": 200,
    #     "response_hash": "<sha256-hex>",
    #     "fetched_at": "2026-04-26T12:34:56Z",
    #     "fetched_via": "<source_id>_client_v1"
    #   }
    proof: dict | None = None


class BaseDataSource(ABC):
    """Abstract base class for all data source clients."""

    source_id: str  # Must match the source_card.id in the database

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @abstractmethod
    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        """Fetch data from this source and write it to output_dir.

        Args:
            params: What data to retrieve (date range, query, etc.)
            output_dir: Directory to write output files into.

        Returns:
            FetchResult with path to the written file and metadata.
        """
        ...

    @abstractmethod
    def supports_query(self, research_question: str) -> bool:
        """Return True if this source can plausibly provide data for the question."""
        ...
