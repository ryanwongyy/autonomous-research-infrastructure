"""SEC EDGAR full-text search client.

Fetches corporate filings from SEC EDGAR EFTS (full-text search)
(https://efts.sec.gov/LATEST/search-index). Free API, no key required.
User-Agent header with company/email required per SEC policy.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.services.data_sources.base import BaseDataSource, FetchParams, FetchResult

logger = logging.getLogger(__name__)

EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"


class EdgarSource(BaseDataSource):
    """Fetches SEC EDGAR filings via full-text search."""

    source_id = "edgar"

    async def fetch(self, params: FetchParams, output_dir: Path) -> FetchResult:
        query = params.query or '"artificial intelligence" OR "machine learning" OR "AI governance"'

        api_params: dict = {
            "q": query,
            "dateRange": "custom",
            "startdt": params.date_range_start or "2020-01-01",
            "enddt": params.date_range_end or "2026-12-31",
            "forms": "10-K,10-Q,8-K,DEF 14A",  # Annual, quarterly, current reports, proxy statements
        }

        try:
            records = await self._search_filings(api_params, params.max_records)
        except Exception as e:
            logger.error("EDGAR fetch failed: %s", e)
            return FetchResult(success=False, error=str(e))

        if not records:
            return FetchResult(
                success=True,
                row_count=0,
                description="No matching EDGAR filings found",
            )

        output_path = output_dir / "edgar_filings.csv"
        columns = [
            "accession_number",
            "filing_date",
            "form_type",
            "company_name",
            "cik",
            "file_description",
            "filing_url",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for filing in records:
                writer.writerow({
                    "accession_number": filing.get("accession_no", ""),
                    "filing_date": filing.get("file_date", ""),
                    "form_type": filing.get("form_type", ""),
                    "company_name": filing.get("entity_name", ""),
                    "cik": filing.get("cik", ""),
                    "file_description": filing.get("file_description", ""),
                    "filing_url": f"https://www.sec.gov/Archives/edgar/data/{filing.get('cik', '')}/{filing.get('accession_no', '').replace('-', '')}/",
                })

        return FetchResult(
            success=True,
            file_path=str(output_path),
            row_count=len(records),
            columns=columns,
            description=f"Fetched {len(records)} SEC EDGAR filings for: {query[:80]}",
        )

    async def _search_filings(
        self, api_params: dict, max_records: int
    ) -> list[dict]:
        records: list[dict] = []
        start = 0
        per_page = min(max_records, 100)

        headers = {
            "User-Agent": "APE-Replica research@ape-replica.org",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            while len(records) < max_records:
                api_params["from"] = start
                api_params["size"] = per_page
                resp = await client.get(EFTS_BASE, params=api_params)
                resp.raise_for_status()
                data = resp.json()

                hits = data.get("hits", {}).get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    source = hit.get("_source", {})
                    records.append(source)

                start += per_page
                total = data.get("hits", {}).get("total", {}).get("value", 0)
                if start >= total or start >= 500:  # Safety cap
                    break

        return records[:max_records]

    def supports_query(self, research_question: str) -> bool:
        rq = research_question.lower()
        keywords = [
            "corporate",
            "company",
            "firm",
            "disclosure",
            "sec",
            "filing",
            "proxy",
            "board",
            "governance",
            "investor",
            "shareholder",
        ]
        return any(kw in rq for kw in keywords)
