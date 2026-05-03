"""Seed the source_cards table with all AI-governance data sources.

Usage:
    python -m seeds.source_cards
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.source_card import SourceCard


# ---------------------------------------------------------------------------
# Source card definitions
# ---------------------------------------------------------------------------

SOURCE_CARDS: list[dict] = [
    # ------------------------------------------------------------------
    # Tier A -- Official Primary Sources
    # ------------------------------------------------------------------
    {
        "id": "federal_register",
        "name": "Federal Register / GovInfo",
        "url": "https://www.govinfo.gov / https://www.federalregister.gov/api",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "api",
        "requires_key": True,
        "canonical_unit": "instrument-by-jurisdiction-by-date",
        "claim_permissions": json.dumps([
            "timing of rules",
            "legal obligations",
            "governance design",
            "textual change",
        ]),
        "claim_prohibitions": json.dumps([
            "compliance or effects by themselves",
        ]),
        "known_traps": json.dumps([
            "binding vs nonbinding confusion",
            "consolidated texts masking enactment dates",
        ]),
        "fragility_score": 0.15,
        "active": True,
    },
    {
        "id": "regulations_gov",
        "name": "Regulations.gov",
        "url": "https://api.regulations.gov",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "api",
        "requires_key": True,
        "canonical_unit": "hearing/witness-statement/comment/docket",
        "claim_permissions": json.dumps([
            "stakeholder positions",
            "agenda setting",
            "participation structure",
            "draft-to-final textual movement",
        ]),
        "claim_prohibitions": json.dumps([
            "causal influence without more evidence",
        ]),
        "known_traps": json.dumps([
            "duplicate comments",
            "coordinated campaigns",
            "missing unpublished materials",
        ]),
        "fragility_score": 0.20,
        "active": True,
    },
    {
        "id": "edgar",
        "name": "SEC EDGAR",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar",
        "tier": "A",
        "source_type": "corporate_filings",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "firm-period/model-release/report/disclosure-event",
        "claim_permissions": json.dumps([
            "disclosed governance structures",
            "risk language",
            "board oversight",
            "reporting behavior",
            "public commitments",
        ]),
        "claim_prohibitions": json.dumps([
            "undisclosed internal safety practice or actual control quality",
        ]),
        "known_traps": json.dumps([
            "boilerplate",
            "strategic disclosure",
            "PR inflation",
            "version drift",
        ]),
        "fragility_score": 0.15,
        "active": True,
    },
    {
        "id": "eur_lex",
        "name": "EUR-Lex (EU Law)",
        "url": "https://eur-lex.europa.eu",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "instrument-by-jurisdiction-by-date",
        "parse_method": "html_extract",
        "claim_permissions": json.dumps([
            "EU legal obligations",
            "regulatory design",
            "textual change",
        ]),
        "claim_prohibitions": json.dumps([
            "member state implementation quality alone",
        ]),
        "known_traps": json.dumps([
            "translation drift",
            "consolidated vs original texts",
        ]),
        "fragility_score": 0.20,
        "active": True,
    },
    {
        "id": "usaspending",
        "name": "USAspending.gov",
        "url": "https://api.usaspending.gov",
        "tier": "A",
        "source_type": "procurement_database",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "contract-notice/award/buyer-year/supplier-year/program-year",
        "claim_permissions": json.dumps([
            "spending",
            "vendor concentration",
            "contract design",
            "safeguard language",
            "diffusion of guardrails",
        ]),
        "claim_prohibitions": json.dumps([
            "actual deployed system performance or agency use in practice",
        ]),
        "known_traps": json.dumps([
            "notice-vs-award confusion",
            "framework contracts",
            "inconsistent identifiers",
            "amendments",
            "AI not explicitly labeled",
        ]),
        "fragility_score": 0.25,
        "active": True,
    },
    {
        "id": "ted",
        "name": "TED (Tenders Electronic Daily, EU)",
        "url": "https://ted.europa.eu",
        "tier": "A",
        "source_type": "procurement_database",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "contract-notice/award",
        "claim_permissions": json.dumps([
            "EU procurement patterns",
            "cross-national procurement comparison",
        ]),
        "claim_prohibitions": json.dumps([
            "contract performance",
        ]),
        "known_traps": json.dumps([
            "language barriers",
            "inconsistent coding",
        ]),
        "fragility_score": 0.30,
        "active": True,
    },
    {
        "id": "courtlistener",
        "name": "CourtListener",
        "url": "https://www.courtlistener.com/api/rest/v4/",
        "tier": "A",
        "source_type": "court_database",
        "access_method": "api",
        "requires_key": True,
        "canonical_unit": "case/order/action/docket-event",
        "claim_permissions": json.dumps([
            "legal reasoning",
            "enforcement priorities",
            "doctrinal movement",
            "institutional response",
        ]),
        "claim_prohibitions": json.dumps([
            "population-level compliance rates or unobserved disputes",
        ]),
        "known_traps": json.dumps([
            "selection bias",
            "opaque settlements",
            "uneven docket coverage",
            "overreading dicta",
        ]),
        "fragility_score": 0.25,
        "active": True,
    },
    {
        "id": "nist_ai_rmf",
        "name": "NIST AI Risk Management Framework",
        "url": "https://www.nist.gov/artificial-intelligence",
        "tier": "A",
        "source_type": "standards_body",
        "access_method": "html_parse",
        "requires_key": False,
        "canonical_unit": "guidance-document/framework-version",
        "parse_method": "html_extract",
        "claim_permissions": json.dumps([
            "governance standards",
            "framework design",
            "evolution of guidance",
        ]),
        "claim_prohibitions": json.dumps([
            "adoption rates or compliance",
        ]),
        "known_traps": json.dumps([
            "versioning",
            "companion documents",
        ]),
        "fragility_score": 0.35,
        "active": True,
    },
    {
        "id": "govinfo_hearings",
        "name": "GovInfo Congressional Hearings",
        "url": "https://www.govinfo.gov/app/collection/chrg",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "hearing/witness-statement",
        "claim_permissions": json.dumps([
            "congressional attention",
            "stakeholder testimony",
            "agenda dynamics",
        ]),
        "claim_prohibitions": json.dumps([
            "legislative influence without linking to outcomes",
        ]),
        "known_traps": json.dumps([
            "selective witness lists",
            "prepared vs actual testimony",
        ]),
        "fragility_score": 0.20,
        "active": True,
    },
    {
        # Mandated by EO 13960 (Dec 2020) — each federal agency
        # publishes a JSON inventory of its AI use cases. Critical
        # for "what AI is the federal government actually using"
        # claims. Covers most of what apep_9afaf116 needed and could
        # not anchor (the paper claimed federal AI deployment via
        # USAspending, which has only spending records).
        "id": "federal_ai_use_cases",
        "name": "Federal AI Use Case Inventory",
        "url": "https://ai.gov/ai-use-cases/",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "bulk_download",
        "requires_key": False,
        "canonical_unit": "use-case-by-agency-by-fiscal-year",
        "claim_permissions": json.dumps([
            "specific agency AI deployments",
            "use case descriptions",
            "stage of deployment",
            "rights-impacting flag",
        ]),
        "claim_prohibitions": json.dumps([
            "performance or accuracy of deployed systems",
            "agency claims not in the disclosed inventory",
        ]),
        "known_traps": json.dumps([
            "voluntary level-of-detail",
            "varying inventory completeness across agencies",
            "naming inconsistency for same system",
        ]),
        "fragility_score": 0.30,
        "active": True,
    },
    {
        # GAO is the audit arm of Congress; its reports are
        # authoritative on government-program performance, including
        # AI procurement and use. Reports often quantify deployment
        # patterns and compliance gaps that the Federal Register
        # alone (rule text) and USAspending (money) cannot.
        "id": "gao_reports",
        "name": "GAO Reports (Government Accountability Office)",
        "url": "https://www.gao.gov/reports-testimonies",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "report-by-id/recommendation",
        "claim_permissions": json.dumps([
            "audited findings on agency program operations",
            "recommendations to agencies",
            "implementation status of prior recommendations",
            "patterns in federal AI use across agencies",
        ]),
        "claim_prohibitions": json.dumps([
            "claims outside the report's scoped audit period",
            "predictions about future enforcement",
        ]),
        "known_traps": json.dumps([
            "scope of the audit may be narrower than the report title",
            "recommendation-vs-finding distinction",
        ]),
        "fragility_score": 0.20,
        "active": True,
    },
    {
        # Executive orders, OSTP guidance, and OMB memoranda. The
        # canonical authority for federal AI policy direction
        # (e.g. EO 13960, EO 14110, the Blueprint for an AI Bill
        # of Rights, OMB M-24-10).
        "id": "whitehouse_ostp",
        "name": "White House OSTP / Executive Orders / OMB Memoranda",
        "url": "https://www.whitehouse.gov/ostp/",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "html_parse",
        "requires_key": False,
        "canonical_unit": "executive-instrument-by-date",
        "claim_permissions": json.dumps([
            "executive policy direction",
            "agency mandates from OMB",
            "high-level governance framework",
            "principles articulated by the executive branch",
        ]),
        "claim_prohibitions": json.dumps([
            "agency implementation quality",
            "downstream behavioral change without separate evidence",
        ]),
        "known_traps": json.dumps([
            "EO superseded by a later EO",
            "principles vs binding requirements distinction",
        ]),
        "fragility_score": 0.25,
        "active": True,
    },
    {
        # USPTO patent filings. Useful for AI invention claims,
        # patent-quality measures, and the tension between AI as
        # invention vs AI as inventor (Thaler v. Vidal, etc.).
        "id": "uspto_patents",
        "name": "USPTO Patent Database",
        "url": "https://developer.uspto.gov/api-catalog",
        "tier": "A",
        "source_type": "government_registry",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "application/patent/family",
        "claim_permissions": json.dumps([
            "filing volume by technology classification",
            "patent grant rates",
            "assignee concentration",
            "claim text and inventor-of-record",
        ]),
        "claim_prohibitions": json.dumps([
            "actual invention novelty",
            "deployment of patented technology",
            "post-grant value or licensing",
        ]),
        "known_traps": json.dumps([
            "AI-related classifications evolve",
            "continuation/divisional families inflate counts",
            "prior-art coverage uneven across decades",
        ]),
        "fragility_score": 0.30,
        "active": True,
    },
    {
        # arXiv — the canonical preprint repository for AI/ML
        # research. Pairs with OpenAlex (citations + venues) for
        # bibliometric work; arXiv is where the LLM should cite
        # specific papers, not just bibliographic indices.
        "id": "arxiv",
        "name": "arXiv (preprint repository)",
        "url": "https://arxiv.org/help/api/index",
        "tier": "A",
        "source_type": "research_index",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "paper/version-by-id",
        "claim_permissions": json.dumps([
            "specific cited works and their content",
            "research direction by category",
            "submission timing of specific findings",
            "version histories of preprints",
        ]),
        "claim_prohibitions": json.dumps([
            "peer-review status (preprints are not peer-reviewed)",
            "downstream citation impact (use openalex)",
        ]),
        "known_traps": json.dumps([
            "papers withdrawn or superseded",
            "category drift",
            "double submissions across categories",
        ]),
        "fragility_score": 0.20,
        "active": True,
    },

    # ------------------------------------------------------------------
    # Tier B -- Structured Public Secondary
    # ------------------------------------------------------------------
    {
        "id": "oecd_ai",
        "name": "OECD.AI Policy Observatory",
        "url": "https://oecd.ai",
        "tier": "B",
        "source_type": "policy_database",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "country-year-policy/jurisdiction-policy",
        "parse_method": "html_extract",
        "claim_permissions": json.dumps([
            "diffusion",
            "clustering",
            "timing",
            "comparative governance design",
        ]),
        "claim_prohibitions": json.dumps([
            "fine doctrinal nuance or implementation quality alone",
        ]),
        "known_traps": json.dumps([
            "coding heterogeneity",
            "database incompleteness",
        ]),
        "fragility_score": 0.30,
        "active": True,
    },
    {
        "id": "openalex",
        "name": "OpenAlex",
        "url": "https://api.openalex.org",
        "tier": "B",
        "source_type": "academic_index",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "paper/patent-family/repository",
        "claim_permissions": json.dumps([
            "research direction",
            "scholarly diffusion",
            "bibliometric patterns",
        ]),
        "claim_prohibitions": json.dumps([
            "proprietary deployment claims",
        ]),
        "known_traps": json.dumps([
            "publication lag",
            "coverage gaps",
        ]),
        "fragility_score": 0.20,
        "active": True,
    },
    {
        "id": "aiid",
        "name": "AI Incident Database",
        "url": "https://incidentdatabase.ai",
        "tier": "B",
        "source_type": "incident_database",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "incident/hazard-event",
        "parse_method": "html_extract",
        "claim_permissions": json.dumps([
            "reported harm categories",
            "timing",
            "response patterns",
            "institutional learning pathways",
        ]),
        "claim_prohibitions": json.dumps([
            "true base-rate or prevalence claims",
        ]),
        "known_traps": json.dumps([
            "media selection",
            "duplicate coverage",
            "changing taxonomies",
            "headline bias",
        ]),
        "fragility_score": 0.35,
        "active": True,
    },
    {
        "id": "stanford_hai",
        "name": "Stanford HAI AI Index",
        "url": "https://hai.stanford.edu/ai-index",
        "tier": "B",
        "source_type": "research_index",
        "access_method": "bulk_download",
        "requires_key": False,
        "canonical_unit": "indicator-year",
        "parse_method": "pdf_extract",
        "claim_permissions": json.dumps([
            "globally sourced indicators",
            "benchmark emphasis",
        ]),
        "claim_prohibitions": json.dumps([
            "independent performance claims when vendor-chosen",
        ]),
        "known_traps": json.dumps([
            "incomparable benchmarks",
            "self-selection",
            "shifting test sets",
        ]),
        "fragility_score": 0.35,
        "active": True,
    },
    {
        "id": "opencorporates",
        "name": "OpenCorporates",
        "url": "https://api.opencorporates.com",
        "tier": "B",
        "source_type": "corporate_registry",
        "access_method": "api",
        "requires_key": True,
        "canonical_unit": "company/officer",
        "claim_permissions": json.dumps([
            "company records",
            "entity resolution",
        ]),
        "claim_prohibitions": json.dumps([
            "internal governance practices",
        ]),
        "known_traps": json.dumps([
            "coverage varies by jurisdiction",
        ]),
        "fragility_score": 0.25,
        "active": True,
    },
    {
        "id": "hugging_face",
        "name": "Hugging Face Hub (model/dataset cards)",
        "url": "https://huggingface.co/api",
        "tier": "B",
        "source_type": "model_registry",
        "access_method": "api",
        "requires_key": False,
        "canonical_unit": "model-card/dataset-card/system-card",
        "claim_permissions": json.dumps([
            "disclosed evaluation practice",
            "governance framing",
            "model documentation patterns",
        ]),
        "claim_prohibitions": json.dumps([
            "actual model capability beyond disclosed benchmarks",
        ]),
        "known_traps": json.dumps([
            "voluntary disclosure",
            "version drift",
            "marketing language",
        ]),
        "fragility_score": 0.30,
        "active": True,
    },
    {
        "id": "gh_archive",
        "name": "GH Archive (GitHub Events)",
        "url": "https://www.gharchive.org",
        "tier": "B",
        "source_type": "code_repository",
        "access_method": "bulk_download",
        "requires_key": False,
        "canonical_unit": "event/repository/commit-stream",
        "claim_permissions": json.dumps([
            "open-source release behavior",
            "collaborative patterns",
        ]),
        "claim_prohibitions": json.dumps([
            "proprietary development",
        ]),
        "known_traps": json.dumps([
            "noisy signals",
            "bot activity",
        ]),
        "fragility_score": 0.35,
        "active": True,
    },

    # ------------------------------------------------------------------
    # Tier C -- Auxiliary (corroboration only)
    # ------------------------------------------------------------------
    {
        "id": "oecd_aim",
        "name": "OECD AI Incidents Monitor",
        "url": "https://oecd.ai/en/incidents",
        "tier": "C",
        "source_type": "incident_database",
        "access_method": "html_parse",
        "requires_key": False,
        "canonical_unit": None,
        "parse_method": "html_extract",
        "required_corroboration": json.dumps({
            "rule": "Cannot anchor core empirical claims alone; use for triangulation only.",
        }),
        "claim_permissions": json.dumps([
            "triangulation of incident patterns",
        ]),
        "claim_prohibitions": json.dumps([
            "anchor core empirical claims alone",
        ]),
        "known_traps": json.dumps([
            "overlap with AIID",
            "different taxonomy",
        ]),
        "fragility_score": 0.50,
        "active": True,
    },
    {
        "id": "news_archives",
        "name": "Quality news archives (general placeholder)",
        "url": None,
        "tier": "C",
        "source_type": "news_archive",
        "access_method": "web_scrape",
        "requires_key": False,
        "canonical_unit": None,
        "required_corroboration": json.dumps({
            "rule": "Cannot anchor core claims; use to motivate research or triangulate timing only.",
        }),
        "claim_permissions": json.dumps([
            "motivate research",
            "triangulate timing",
        ]),
        "claim_prohibitions": json.dumps([
            "anchor core claims",
        ]),
        "known_traps": json.dumps([
            "selection bias",
            "framing effects",
        ]),
        "fragility_score": 0.60,
        "active": True,
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

async def seed_source_cards() -> None:
    """Insert or update every source card in the registry."""
    await init_db()

    async with async_session() as session:
        async with session.begin():
            for card_data in SOURCE_CARDS:
                card_id = card_data["id"]
                result = await session.execute(
                    select(SourceCard).where(SourceCard.id == card_id)
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    session.add(SourceCard(**card_data))
                    print(f"  [+] Created source card: {card_id}")
                else:
                    for key, value in card_data.items():
                        if key != "id":
                            setattr(existing, key, value)
                    print(f"  [~] Updated source card: {card_id}")

    print(f"\nSeeded {len(SOURCE_CARDS)} source cards.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(seed_source_cards())
