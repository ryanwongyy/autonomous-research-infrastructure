"""OpenAlex API client.

Fetches academic papers, citations, and research trends from OpenAlex
(https://docs.openalex.org). Free API, no key required. Polite pool
available by adding email to requests.
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

API_BASE = "https://api.openalex.org"


class OpenAlexSource(BaseDataSource):
    """Fetches academic works from OpenAlex."""

    source_id = "openalex"

    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        query = params.query or "artificial intelligence governance"

        api_params: dict = {
            "search": query,
            "per_page": min(params.max_records, 200),  # OpenAlex max per page
            "sort": "cited_by_count:desc",
            "select": "id,doi,title,publication_year,cited_by_count,type,open_access,authorships,concepts,primary_location",
        }

        if params.date_range_start and params.date_range_end:
            start_year = params.date_range_start[:4]
            end_year = params.date_range_end[:4]
            api_params["filter"] = f"publication_year:{start_year}-{end_year}"
        elif params.date_range_start:
            start_year = params.date_range_start[:4]
            api_params["filter"] = f"publication_year:{start_year}-"

        # Use polite pool if email available
        if self.api_key:
            api_params["mailto"] = self.api_key

        try:
            records, proof = await self._paginated_fetch(api_params, params.max_records)
        except Exception as e:
            logger.error("OpenAlex fetch failed: %s", e)
            return FetchResult(success=False, error=str(e))

        if not records:
            return FetchResult(
                success=True,
                row_count=0,
                description="No matching OpenAlex works found",
                proof=proof,
            )

        output_path = output_dir / "openalex_works.csv"
        columns = [
            "openalex_id",
            "doi",
            "title",
            "publication_year",
            "cited_by_count",
            "type",
            "is_oa",
            "first_author",
            "journal",
            "top_concept",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for work in records:
                authorships = work.get("authorships") or []
                first_author = ""
                if authorships:
                    author_obj = authorships[0].get("author", {})
                    first_author = author_obj.get("display_name", "")

                primary_loc = work.get("primary_location") or {}
                source = primary_loc.get("source") or {}
                journal = source.get("display_name", "")

                concepts = work.get("concepts") or []
                top_concept = concepts[0].get("display_name", "") if concepts else ""

                oa = work.get("open_access") or {}

                writer.writerow(
                    {
                        "openalex_id": work.get("id", ""),
                        "doi": work.get("doi", ""),
                        "title": work.get("title", ""),
                        "publication_year": work.get("publication_year", ""),
                        "cited_by_count": work.get("cited_by_count", 0),
                        "type": work.get("type", ""),
                        "is_oa": oa.get("is_oa", False),
                        "first_author": first_author,
                        "journal": journal,
                        "top_concept": top_concept,
                    }
                )

        return FetchResult(
            success=True,
            file_path=str(output_path),
            row_count=len(records),
            columns=columns,
            description=f"Fetched {len(records)} academic works from OpenAlex for: {query[:80]}",
            proof=proof,
        )

    async def _paginated_fetch(
        self, api_params: dict, max_records: int
    ) -> tuple[list[dict], dict | None]:
        """Returns ``(records, proof)``; ``proof`` is built from the first page."""
        records: list[dict] = []
        cursor = "*"
        proof: dict | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(records) < max_records:
                api_params["cursor"] = cursor
                resp = await client.get(f"{API_BASE}/works", params=api_params)
                resp.raise_for_status()
                # Build a provenance proof from the FIRST successful page.
                if proof is None:
                    proof = make_http_proof(
                        request_url=str(resp.url),
                        response_status=resp.status_code,
                        response_body=resp.content,
                        fetched_via="openalex_client_v1",
                    )
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    break

                records.extend(results)

                meta = data.get("meta", {})
                cursor = meta.get("next_cursor")
                if not cursor:
                    break

                # Safety cap: 5 pages max (200 * 5 = 1000 records)
                if len(records) >= min(max_records, 1000):
                    break

        return records[:max_records], proof

    def supports_query(self, research_question: str) -> bool:
        rq = research_question.lower()
        keywords = [
            "research",
            "academic",
            "paper",
            "literature",
            "citation",
            "publication",
            "scholarly",
            "study",
            "journal",
        ]
        return any(kw in rq for kw in keywords)
