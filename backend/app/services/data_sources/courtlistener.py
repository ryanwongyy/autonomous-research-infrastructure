"""CourtListener API client.

Fetches US court opinions and dockets from the CourtListener API v4
(https://www.courtlistener.com/api/rest/v4/).

Requires a free API key from https://www.courtlistener.com/sign-in/.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.services.data_sources.base import BaseDataSource, FetchParams, FetchResult

logger = logging.getLogger(__name__)

API_BASE = "https://www.courtlistener.com/api/rest/v4"


class CourtListenerSource(BaseDataSource):
    """Fetches court opinions from CourtListener."""

    source_id = "courtlistener"

    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        if not self.api_key:
            return FetchResult(
                success=False,
                error="CourtListener requires an API key (set COURTLISTENER_API_KEY)",
            )

        query = params.query or "artificial intelligence"

        api_params: dict = {
            "q": query,
            "order_by": "dateFiled desc",
            "page_size": min(params.max_records, 20),
        }

        if params.date_range_start:
            api_params["filed_after"] = params.date_range_start
        if params.date_range_end:
            api_params["filed_before"] = params.date_range_end

        headers = {
            "Authorization": f"Token {self.api_key}",
        }

        try:
            records = await self._paginated_fetch(api_params, headers, params.max_records)
        except Exception as e:
            logger.error("CourtListener fetch failed: %s", e)
            return FetchResult(success=False, error=str(e))

        if not records:
            return FetchResult(
                success=True,
                row_count=0,
                description="No matching CourtListener opinions found",
            )

        output_path = output_dir / "courtlistener_opinions.csv"
        columns = [
            "opinion_id",
            "case_name",
            "court",
            "date_filed",
            "citation",
            "type",
            "status",
            "url",
            "snippet",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for opinion in records:
                cluster = opinion.get("cluster", {}) or {}
                snippet = opinion.get("snippet") or opinion.get("plain_text", "") or ""
                writer.writerow(
                    {
                        "opinion_id": opinion.get("id", ""),
                        "case_name": cluster.get("case_name", opinion.get("case_name", "")),
                        "court": opinion.get("court", ""),
                        "date_filed": cluster.get("date_filed", opinion.get("date_filed", "")),
                        "citation": cluster.get("citation_string", ""),
                        "type": opinion.get("type", ""),
                        "status": cluster.get("precedential_status", ""),
                        "url": f"https://www.courtlistener.com{opinion.get('absolute_url', '')}",
                        "snippet": snippet[:500] if snippet else "",
                    }
                )

        return FetchResult(
            success=True,
            file_path=str(output_path),
            row_count=len(records),
            columns=columns,
            description=f"Fetched {len(records)} court opinions for: {query[:80]}",
        )

    async def _paginated_fetch(
        self, api_params: dict, headers: dict, max_records: int
    ) -> list[dict]:
        records: list[dict] = []
        next_url: str | None = f"{API_BASE}/search/"

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            page = 0
            while next_url and len(records) < max_records:
                if page == 0:
                    resp = await client.get(next_url, params=api_params)
                else:
                    resp = await client.get(next_url)
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    break

                records.extend(results)
                next_url = data.get("next")
                page += 1

                if page >= 10:  # Safety cap
                    break

        return records[:max_records]

    def supports_query(self, research_question: str) -> bool:
        rq = research_question.lower()
        keywords = [
            "court",
            "litigation",
            "judicial",
            "lawsuit",
            "ruling",
            "opinion",
            "case law",
            "legal",
            "enforcement",
        ]
        return any(kw in rq for kw in keywords)
