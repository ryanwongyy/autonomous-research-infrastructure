"""Federal Register API client.

Fetches US federal rules, proposed rules, notices, and executive orders
from the Federal Register API (https://www.federalregister.gov/developers/api/v1).

Free API, no key required for basic access. Rate limited to ~1000 req/hour.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.services.data_sources.base import BaseDataSource, FetchParams, FetchResult

logger = logging.getLogger(__name__)

API_BASE = "https://www.federalregister.gov/api/v1"

# Document types relevant to AI governance research
AI_GOVERNANCE_TERMS = [
    "artificial intelligence",
    "machine learning",
    "algorithmic",
    "automated decision",
    "AI system",
    "AI governance",
    "AI safety",
    "AI risk",
]


class FederalRegisterSource(BaseDataSource):
    """Fetches regulatory documents from the Federal Register API."""

    source_id = "federal_register"

    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        query = params.query or " OR ".join(f'"{t}"' for t in AI_GOVERNANCE_TERMS[:3])

        api_params: dict = {
            "conditions[term]": query,
            "per_page": min(params.max_records, 1000),
            "order": "newest",
            "fields[]": [
                "document_number",
                "title",
                "type",
                "abstract",
                "publication_date",
                "agencies",
                "action",
                "dates",
                "effective_on",
                "citation",
                "html_url",
            ],
        }

        if params.date_range_start:
            api_params["conditions[publication_date][gte]"] = params.date_range_start
        if params.date_range_end:
            api_params["conditions[publication_date][lte]"] = params.date_range_end

        try:
            records = await self._paginated_fetch(api_params, params.max_records)
        except Exception as e:
            logger.error("Federal Register fetch failed: %s", e)
            return FetchResult(success=False, error=str(e))

        if not records:
            return FetchResult(
                success=True,
                row_count=0,
                description="No matching Federal Register documents found",
            )

        # Write to CSV
        output_path = output_dir / "federal_register.csv"
        columns = [
            "document_number",
            "title",
            "type",
            "publication_date",
            "agency",
            "action",
            "effective_on",
            "citation",
            "url",
            "abstract_excerpt",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for doc in records:
                agencies = doc.get("agencies") or []
                agency_names = ", ".join(
                    a.get("name", "") for a in agencies if isinstance(a, dict)
                )
                abstract = doc.get("abstract") or ""
                writer.writerow({
                    "document_number": doc.get("document_number", ""),
                    "title": doc.get("title", ""),
                    "type": doc.get("type", ""),
                    "publication_date": doc.get("publication_date", ""),
                    "agency": agency_names,
                    "action": doc.get("action", ""),
                    "effective_on": doc.get("effective_on", ""),
                    "citation": doc.get("citation", ""),
                    "url": doc.get("html_url", ""),
                    "abstract_excerpt": abstract[:500] if abstract else "",
                })

        return FetchResult(
            success=True,
            file_path=str(output_path),
            row_count=len(records),
            columns=columns,
            description=f"Fetched {len(records)} Federal Register documents for query: {query[:80]}",
        )

    async def _paginated_fetch(
        self, api_params: dict, max_records: int
    ) -> list[dict]:
        """Fetch documents with pagination."""
        records: list[dict] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(records) < max_records:
                api_params["page"] = page
                resp = await client.get(f"{API_BASE}/documents.json", params=api_params)
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    break

                records.extend(results)
                page += 1

                # Respect pagination limits
                total_pages = data.get("total_pages", 1)
                if page > total_pages or page > 10:  # Safety cap: 10 pages max
                    break

        return records[:max_records]

    def supports_query(self, research_question: str) -> bool:
        rq = research_question.lower()
        keywords = [
            "regulation",
            "federal",
            "rule",
            "policy",
            "executive order",
            "government",
            "agency",
            "compliance",
            "regulatory",
            "legislation",
        ]
        return any(kw in rq for kw in keywords)
