import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.domain_config import DomainConfig
from app.schemas.config import CategoryInfo, DomainConfigResponse, DomainConfigUpdate
from app.utils import safe_json_loads

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/config/domains", response_model=list[DomainConfigResponse])
async def list_domains(db: AsyncSession = Depends(get_db)):
    results = (await db.execute(select(DomainConfig))).scalars().all()
    responses = []
    for dc in results:
        cats = safe_json_loads(dc.categories, [])
        methods = safe_json_loads(dc.methods, [])
        responses.append(
            DomainConfigResponse(
                id=dc.id,
                name=dc.name,
                description=dc.description,
                analysis_tool=dc.analysis_tool,
                judge_model=dc.judge_model,
                generation_model=dc.generation_model,
                categories=[CategoryInfo(**c) for c in cats],
                methods=methods,
                active=dc.active,
            )
        )
    return responses


@router.get("/config/domains/{domain_id}", response_model=DomainConfigResponse)
async def get_domain(domain_id: str, db: AsyncSession = Depends(get_db)):
    dc = (await db.execute(select(DomainConfig).where(DomainConfig.id == domain_id))).scalar_one_or_none()
    if not dc:
        raise HTTPException(status_code=404, detail="Domain config not found")

    cats = safe_json_loads(dc.categories, [])
    methods = safe_json_loads(dc.methods, [])
    return DomainConfigResponse(
        id=dc.id,
        name=dc.name,
        description=dc.description,
        analysis_tool=dc.analysis_tool,
        judge_model=dc.judge_model,
        generation_model=dc.generation_model,
        categories=[CategoryInfo(**c) for c in cats],
        methods=methods,
        active=dc.active,
    )


@router.put("/config/domains/{domain_id}", response_model=DomainConfigResponse)
async def update_domain(domain_id: str, update: DomainConfigUpdate, db: AsyncSession = Depends(get_db)):
    dc = (await db.execute(select(DomainConfig).where(DomainConfig.id == domain_id))).scalar_one_or_none()
    if not dc:
        raise HTTPException(status_code=404, detail="Domain config not found")

    updatable = {"name", "description", "judge_model", "generation_model", "active"}
    for field, value in update.model_dump(exclude_unset=True).items():
        if field not in updatable:
            continue
        setattr(dc, field, value)

    try:
        await db.commit()
        await db.refresh(dc)
    except Exception:
        await db.rollback()
        logger.exception("Failed to update domain config %s", domain_id)
        raise HTTPException(status_code=500, detail="Failed to update domain config")

    cats = safe_json_loads(dc.categories, [])
    methods = safe_json_loads(dc.methods, [])
    return DomainConfigResponse(
        id=dc.id,
        name=dc.name,
        description=dc.description,
        analysis_tool=dc.analysis_tool,
        judge_model=dc.judge_model,
        generation_model=dc.generation_model,
        categories=[CategoryInfo(**c) for c in cats],
        methods=methods,
        active=dc.active,
    )


@router.get("/config/models")
async def list_models():
    return {
        "providers": {
            "anthropic": {
                "models": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
            },
            "openai": {
                "models": ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"],
            },
            "google": {
                "models": ["gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
            },
        }
    }
