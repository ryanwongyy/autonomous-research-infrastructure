import json
import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.database import async_session
from app.models.domain_config import DomainConfig
from app.services.llm.router import get_generation_provider
from app.utils import safe_json_loads

logger = logging.getLogger(__name__)


@dataclass
class ResearchIdea:
    title: str
    abstract: str
    research_question: str
    identification_strategy: str
    data_sources: list[str]
    category: str | None
    country: str | None
    method: str


IDEA_PROMPT = """You are an autonomous research agent generating a novel research idea.

Domain: {domain_name}
Description: {domain_description}

Available data sources:
{data_sources}

Available methods:
{methods}

Categories:
{categories}

Generate a novel, rigorous research idea with:
1. A specific, testable research question
2. A credible identification strategy (e.g., DiD, RDD, IV)
3. Clear data requirements from the available sources
4. Policy relevance

Respond in JSON format:
{{
    "title": "Paper title",
    "abstract": "150-word abstract",
    "research_question": "Specific question",
    "identification_strategy": "Detailed strategy description",
    "data_sources": ["source1", "source2"],
    "category": "category_slug",
    "country": "country name or null",
    "method": "DiD or RDD or IV etc"
}}"""


async def generate_research_idea(domain_config_id: str) -> ResearchIdea:
    """Generate a novel research idea using the configured LLM."""
    async with async_session() as db:
        config = (
            await db.execute(select(DomainConfig).where(DomainConfig.id == domain_config_id))
        ).scalar_one()

    data_sources = safe_json_loads(config.data_sources, [])
    methods = safe_json_loads(config.methods, [])
    categories = safe_json_loads(config.categories, [])

    provider, model = await get_generation_provider()

    prompt = IDEA_PROMPT.format(
        domain_name=config.name,
        domain_description=config.description or "",
        data_sources="\n".join(f"- {ds.get('name', ds)}" for ds in data_sources)
        if data_sources
        else "None configured",
        methods=", ".join(methods) if methods else "Any causal inference method",
        categories="\n".join(f"- {c.get('name', c)}" for c in categories)
        if categories
        else "General",
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.8,
        max_tokens=2048,
    )

    # Parse JSON response
    try:
        # Find JSON in response
        start = response.index("{")
        end = response.rindex("}") + 1
        data = json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.error("Failed to parse idea response: %s", response[:500])
        # Fallback
        data = {
            "title": "Generated Research Paper",
            "abstract": response[:500],
            "research_question": "TBD",
            "identification_strategy": "TBD",
            "data_sources": [],
            "category": None,
            "country": None,
            "method": "DiD",
        }

    return ResearchIdea(
        title=data["title"],
        abstract=data["abstract"],
        research_question=data["research_question"],
        identification_strategy=data["identification_strategy"],
        data_sources=data.get("data_sources", []),
        category=data.get("category"),
        country=data.get("country"),
        method=data.get("method", "DiD"),
    )
