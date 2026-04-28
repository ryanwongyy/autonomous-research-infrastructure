"""Data fetcher for paper generation.

Dispatches to real API clients via the data source registry.

Behaviour depends on `settings.data_mode`:
  - "real"       — strict: raise `DataFetchError` if no source returns real
                   data. No synthetic placeholder is ever produced.
  - "permissive" — allow a synthetic placeholder CSV when no source returns
                   data. Useful for local dev; produces papers that are NOT
                   grounded in real data.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.services.data_sources.base import FetchParams
from app.services.data_sources.registry import fetch_from_source
from app.services.paper_generation.idea_generator import ResearchIdea

logger = logging.getLogger(__name__)


class DataFetchError(RuntimeError):
    """Raised in DATA_MODE=real when no source returns real data.

    The pipeline orchestrator catches this and records a stage failure
    rather than producing a paper grounded in synthetic data.
    """


# Maps source_card IDs to Settings attribute names that hold the API key.
_API_KEY_MAP: dict[str, str] = {
    "regulations_gov": "regulations_gov_api_key",
    "courtlistener": "courtlistener_api_key",
    "openalex": "openalex_email",
}


def _api_key_for(source_id: str) -> str | None:
    attr = _API_KEY_MAP.get(source_id)
    if attr:
        return getattr(settings, attr, None) or None
    return None


@dataclass
class DataResult:
    success: bool
    files: list[str] = field(default_factory=list)
    description: str = ""
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    error: str | None = None


async def fetch_data(idea: ResearchIdea, paper_dir: str) -> DataResult:
    """Fetch real data from public APIs based on the research idea."""
    data_dir = os.path.join(paper_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    output_path = Path(data_dir)

    fetched_files: list[str] = []
    total_rows = 0
    all_columns: list[str] = []

    params = FetchParams(
        query=idea.research_question,
        max_records=500,
    )

    for source_name in idea.data_sources:
        source_id = _normalize_source_id(source_name)
        try:
            result = await fetch_from_source(
                source_id,
                params,
                output_path,
                api_key=_api_key_for(source_id),
            )
            if result.success and result.file_path:
                fetched_files.append(result.file_path)
                total_rows += result.row_count
                if result.columns:
                    all_columns = result.columns  # keep last set
                logger.info("Fetched %d rows from %s", result.row_count, source_id)
            elif result.error:
                logger.warning("Source %s failed: %s", source_id, result.error)
        except Exception as e:
            logger.warning("Failed to fetch from %s: %s", source_name, e)

    if not fetched_files:
        if settings.data_mode == "real":
            raise DataFetchError(
                f"No real data fetched for idea '{idea.title}'. "
                f"Tried sources: {idea.data_sources!r}. "
                f"DATA_MODE=real disallows synthetic placeholder data; "
                f"set DATA_MODE=permissive (NOT recommended in production) "
                f"to allow placeholder CSV in local development."
            )

        # ── permissive mode: emit synthetic placeholder, but log loudly ──
        logger.error(
            "DATA_MODE=permissive: emitting SYNTHETIC placeholder CSV for "
            "idea '%s'. Papers built on this data are NOT grounded in real "
            "sources and MUST NOT be released to the public.",
            idea.title,
        )
        placeholder_path = os.path.join(data_dir, "placeholder.csv")
        with open(placeholder_path, "w") as f:
            f.write("id,year,treatment,outcome,control_var1,control_var2\n")
            for i in range(100):
                year = 2015 + (i % 10)
                treatment = 1 if i > 50 else 0
                outcome = 10 + treatment * 2 + (i % 5) * 0.5
                f.write(f"{i},{year},{treatment},{outcome:.2f},{i * 0.1:.2f},{i * 0.05:.2f}\n")
        fetched_files.append(placeholder_path)
        total_rows = 100
        all_columns = [
            "id",
            "year",
            "treatment",
            "outcome",
            "control_var1",
            "control_var2",
        ]

    return DataResult(
        success=True,
        files=fetched_files,
        description=f"Fetched {len(fetched_files)} data file(s) for: {idea.title}",
        row_count=total_rows,
        columns=all_columns,
    )


def _normalize_source_id(name: str) -> str:
    """Normalize a source name from the LLM to a source_card ID."""
    name = name.strip().lower()
    # Direct match
    if name in {
        "federal_register",
        "regulations_gov",
        "edgar",
        "usaspending",
        "openalex",
        "courtlistener",
    }:
        return name
    # Common aliases
    aliases: dict[str, str] = {
        "federal register": "federal_register",
        "fed register": "federal_register",
        "govinfo": "federal_register",
        "regulations.gov": "regulations_gov",
        "sec edgar": "edgar",
        "sec": "edgar",
        "usaspending": "usaspending",
        "usa spending": "usaspending",
        "openalex": "openalex",
        "open alex": "openalex",
        "court listener": "courtlistener",
        "courtlistener": "courtlistener",
        "fred": "fred",
    }
    return aliases.get(name, name)
