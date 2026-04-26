"""Regulations.gov API client.

Fetches federal rulemaking dockets, comments, and documents from the
Regulations.gov API v4 (https://api.regulations.gov/v4/).

Requires a free API key from https://open.gsa.gov/api/regulationsgov/.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.services.data_sources.base import BaseDataSource, FetchParams, FetchResult

logger = logging.getLogger(__name__)

API_BASE = "https://api.regulations.gov/v4"


class RegulationsGovSource(BaseDataSource):
    """Fetches regulatory documents from Regulations.gov."""

    source_id = "regulations_gov"

    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        if not self.api_key:
            return FetchResult(
                success=False,
                error="Regulations.gov requires an API key (set REGULATIONS_GOV_API_KEY)",
            )

        query = params.query or "artificial intelligence"

        api_params: dict = {
            "filter[searchTerm]": query,
            "sort": "-postedDate",
            "page[size]": min(params.max_records, 250),
            "api_key": self.api_key,
        }

        if params.date_range_start:
            api_params["filter[postedDate][ge]"] = params.date_range_start
        if params.date_range_end:
            api_params["filter[postedDate][le]"] = params.date_range_end

        try:
            records = await self._paginated_fetch(api_params, params.max_records)
        except Exception as e:
            logger.error("Regulations.gov fetch failed: %s", e)
            return FetchResult(success=False, error=str(e))

        if not records:
            return FetchResult(
                success=True,
                row_count=0,
                description="No matching Regulations.gov documents found",
            )

        output_path = output_dir / "regulations_gov.csv"
        columns = [
            "document_id",
            "document_type",
            "title",
            "posted_date",
            "agency_id",
            "docket_id",
            "comment_start_date",
            "comment_end_date",
            "url",
            "excerpt",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for doc in records:
                attrs = doc.get("attributes", {})
                excerpt = attrs.get("highlightedContent") or attrs.get("title") or ""
                writer.writerow(
                    {
                        "document_id": doc.get("id", ""),
                        "document_type": attrs.get("documentType", ""),
                        "title": attrs.get("title", ""),
                        "posted_date": attrs.get("postedDate", ""),
                        "agency_id": attrs.get("agencyId", ""),
                        "docket_id": attrs.get("docketId", ""),
                        "comment_start_date": attrs.get("commentStartDate", ""),
                        "comment_end_date": attrs.get("commentEndDate", ""),
                        "url": f"https://www.regulations.gov/document/{doc.get('id', '')}",
                        "excerpt": excerpt[:500] if excerpt else "",
                    }
                )

        return FetchResult(
            success=True,
            file_path=str(output_path),
            row_count=len(records),
            columns=columns,
            description=f"Fetched {len(records)} Regulations.gov documents for: {query[:80]}",
        )

    async def _paginated_fetch(self, api_params: dict, max_records: int) -> list[dict]:
        records: list[dict] = []
        page = 1

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(records) < max_records:
                api_params["page[number]"] = page
                resp = await client.get(
                    f"{API_BASE}/documents",
                    params=api_params,
                )
                resp.raise_for_status()
                data = resp.json()

                results = data.get("data", [])
                if not results:
                    break

                records.extend(results)
                page += 1

                meta = data.get("meta", {})
                if not meta.get("hasNextPage", False):
                    break
                if page > 10:  # Safety cap
                    break

        return records[:max_records]

    def supports_query(self, research_question: str) -> bool:
        rq = research_question.lower()
        keywords = [
            "regulation",
            "rulemaking",
            "comment",
            "docket",
            "public comment",
            "stakeholder",
            "notice",
            "proposed rule",
        ]
        return any(kw in rq for kw in keywords)
