"""Data source registry.

Maps source_card IDs to their corresponding API client classes and provides
a dispatcher that the data fetcher can call without knowing which API to hit.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.services.data_sources.base import BaseDataSource, FetchParams, FetchResult
from app.services.data_sources.edgar import EdgarSource
from app.services.data_sources.federal_register import FederalRegisterSource
from app.services.data_sources.openalex import OpenAlexSource
from app.services.data_sources.usaspending import USASpendingSource

logger = logging.getLogger(__name__)

# Maps source_card.id → client class
_SOURCE_CLASSES: dict[str, type[BaseDataSource]] = {
    "federal_register": FederalRegisterSource,
    "edgar": EdgarSource,
    "usaspending": USASpendingSource,
    "openalex": OpenAlexSource,
}

# Lazy import to avoid circular imports at module load time
_LAZY_SOURCES: dict[str, tuple[str, str]] = {
    "regulations_gov": (
        "app.services.data_sources.regulations_gov",
        "RegulationsGovSource",
    ),
    "courtlistener": (
        "app.services.data_sources.courtlistener",
        "CourtListenerSource",
    ),
}


def _resolve_class(source_id: str) -> type[BaseDataSource] | None:
    """Return the client class for a source_id, lazily importing if needed."""
    if source_id in _SOURCE_CLASSES:
        return _SOURCE_CLASSES[source_id]

    if source_id in _LAZY_SOURCES:
        module_path, class_name = _LAZY_SOURCES[source_id]
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        _SOURCE_CLASSES[source_id] = cls  # cache for next call
        return cls

    return None


def get_source(source_id: str, api_key: str | None = None) -> BaseDataSource | None:
    """Instantiate and return a data source client by source_card ID."""
    cls = _resolve_class(source_id)
    if cls is None:
        return None
    return cls(api_key=api_key)


def list_available_sources() -> list[str]:
    """Return all source IDs that have a working API client."""
    return sorted(set(_SOURCE_CLASSES) | set(_LAZY_SOURCES))


async def fetch_from_source(
    source_id: str,
    params: FetchParams,
    output_dir: Path,
    api_key: str | None = None,
) -> FetchResult:
    """High-level dispatcher: fetch data from a named source."""
    client = get_source(source_id, api_key=api_key)
    if client is None:
        logger.info("No API client for source: %s", source_id)
        return FetchResult(
            success=False,
            error=f"No API client implemented for source: {source_id}",
        )
    return await client.fetch(params, output_dir)
