"""USAspending.gov API client.

Fetches US government contract and grant data from USAspending.gov
(https://api.usaspending.gov). Free API, no key required.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.services.data_sources.base import (
    BaseDataSource,
    FetchParams,
    FetchResult,
    make_http_proof,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.usaspending.gov/api/v2"


class USASpendingSource(BaseDataSource):
    """Fetches federal spending data from USAspending.gov."""

    source_id = "usaspending"

    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        query = params.query or "artificial intelligence"

        body: dict = {
            "filters": {
                "keywords": [query],
                "time_period": [],
                "award_type_codes": ["A", "B", "C", "D"],  # Contracts
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Award Amount",
                "Total Outlays",
                "Description",
                "Start Date",
                "End Date",
                "Awarding Agency",
                "Awarding Sub Agency",
                "Contract Award Type",
                "recipient_id",
                "internal_id",
            ],
            "limit": min(params.max_records, 100),
            "page": 1,
            "sort": "Award Amount",
            "order": "desc",
        }

        if params.date_range_start and params.date_range_end:
            body["filters"]["time_period"].append(
                {
                    "start_date": params.date_range_start,
                    "end_date": params.date_range_end,
                }
            )
        elif params.date_range_start:
            body["filters"]["time_period"].append(
                {
                    "start_date": params.date_range_start,
                    "end_date": "2026-12-31",
                }
            )

        try:
            records, proof = await self._paginated_fetch(body, params.max_records)
        except Exception as e:
            logger.error("USAspending fetch failed: %s", e)
            return FetchResult(success=False, error=str(e))

        if not records:
            return FetchResult(
                success=True,
                row_count=0,
                description="No matching USAspending awards found",
                proof=proof,
            )

        output_path = output_dir / "usaspending_awards.csv"
        columns = [
            "award_id",
            "recipient_name",
            "award_amount",
            "total_outlays",
            "description",
            "start_date",
            "end_date",
            "awarding_agency",
            "awarding_sub_agency",
            "award_type",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for award in records:
                desc = award.get("Description") or ""
                writer.writerow(
                    {
                        "award_id": award.get("Award ID", ""),
                        "recipient_name": award.get("Recipient Name", ""),
                        "award_amount": award.get("Award Amount", 0),
                        "total_outlays": award.get("Total Outlays", 0),
                        "description": desc[:500] if desc else "",
                        "start_date": award.get("Start Date", ""),
                        "end_date": award.get("End Date", ""),
                        "awarding_agency": award.get("Awarding Agency", ""),
                        "awarding_sub_agency": award.get("Awarding Sub Agency", ""),
                        "award_type": award.get("Contract Award Type", ""),
                    }
                )

        return FetchResult(
            success=True,
            file_path=str(output_path),
            row_count=len(records),
            columns=columns,
            description=f"Fetched {len(records)} USAspending awards for: {query[:80]}",
            proof=proof,
        )

    async def _paginated_fetch(
        self, body: dict, max_records: int
    ) -> tuple[list[dict], dict | None]:
        """Returns ``(records, proof)``; ``proof`` is built from the first page."""
        records: list[dict] = []
        proof: dict | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(records) < max_records:
                resp = await client.post(
                    f"{API_BASE}/search/spending_by_award/",
                    json=body,
                )
                resp.raise_for_status()
                if proof is None:
                    proof = make_http_proof(
                        request_url=str(resp.url),
                        response_status=resp.status_code,
                        response_body=resp.content,
                        fetched_via="usaspending_client_v1",
                    )
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    break

                records.extend(results)
                body["page"] = body.get("page", 1) + 1

                if not data.get("page_metadata", {}).get("hasNext", False):
                    break
                if body["page"] > 10:  # Safety cap
                    break

        return records[:max_records], proof

    def supports_query(self, research_question: str) -> bool:
        rq = research_question.lower()
        keywords = [
            "spending",
            "contract",
            "procurement",
            "grant",
            "budget",
            "federal",
            "government",
            "vendor",
            "acquisition",
        ]
        return any(kw in rq for kw in keywords)
