"""Versioned prompt registry. Every hardcoded prompt becomes a fallback; DB-stored versions take precedence."""

from __future__ import annotations

import difflib
import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_version import PromptVersion

logger = logging.getLogger(__name__)


async def register_prompt(
    session: AsyncSession,
    target_type: str,
    target_key: str,
    prompt_text: str,
    experiment_id: int | None = None,
) -> PromptVersion:
    """Register a new prompt version. Auto-increments version number."""
    # Find current max version for this target
    max_version_result = await session.execute(
        select(func.max(PromptVersion.version)).where(
            PromptVersion.target_type == target_type,
            PromptVersion.target_key == target_key,
        )
    )
    max_version = max_version_result.scalar()
    new_version = (max_version or 0) + 1

    # Compute diff from previous version if one exists
    diff_text: str | None = None
    if max_version is not None:
        prev_result = await session.execute(
            select(PromptVersion).where(
                PromptVersion.target_type == target_type,
                PromptVersion.target_key == target_key,
                PromptVersion.version == max_version,
            )
        )
        prev = prev_result.scalar_one_or_none()
        if prev is not None:
            diff_text = await compute_prompt_diff(prev.prompt_text, prompt_text)

    prompt_version = PromptVersion(
        target_type=target_type,
        target_key=target_key,
        version=new_version,
        prompt_text=prompt_text,
        diff_from_previous=diff_text,
        experiment_id=experiment_id,
        is_active=False,
    )
    session.add(prompt_version)
    await session.flush()

    logger.info(
        "Registered prompt version %s for %s/%s",
        new_version, target_type, target_key,
    )
    return prompt_version


async def get_active_prompt(
    session: AsyncSession,
    target_type: str,
    target_key: str,
) -> str | None:
    """Get the active prompt text for a target. Returns None if no DB override (use hardcoded default)."""
    result = await session.execute(
        select(PromptVersion.prompt_text).where(
            PromptVersion.target_type == target_type,
            PromptVersion.target_key == target_key,
            PromptVersion.is_active.is_(True),
        )
    )
    row = result.scalar_one_or_none()
    return row


async def activate_prompt_version(
    session: AsyncSession,
    version_id: int,
) -> PromptVersion:
    """Activate a specific prompt version. Deactivates all other versions for the same target."""
    result = await session.execute(
        select(PromptVersion).where(PromptVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise ValueError(f"Prompt version {version_id} not found")

    # Deactivate all other versions for the same target
    await session.execute(
        update(PromptVersion)
        .where(
            PromptVersion.target_type == version.target_type,
            PromptVersion.target_key == version.target_key,
            PromptVersion.id != version_id,
        )
        .values(is_active=False)
    )

    version.is_active = True

    logger.info(
        "Activated prompt version %s (v%s) for %s/%s",
        version.id, version.version, version.target_type, version.target_key,
    )
    return version


async def rollback_prompt(
    session: AsyncSession,
    target_type: str,
    target_key: str,
) -> PromptVersion | None:
    """Rollback: deactivate current, reactivate previous version."""
    # Find the currently active version
    active_result = await session.execute(
        select(PromptVersion).where(
            PromptVersion.target_type == target_type,
            PromptVersion.target_key == target_key,
            PromptVersion.is_active.is_(True),
        )
    )
    active_version = active_result.scalar_one_or_none()
    if active_version is None:
        logger.warning("No active prompt to rollback for %s/%s", target_type, target_key)
        return None

    # Deactivate the current version
    active_version.is_active = False

    # Find the previous version (by version number - 1)
    prev_result = await session.execute(
        select(PromptVersion).where(
            PromptVersion.target_type == target_type,
            PromptVersion.target_key == target_key,
            PromptVersion.version == active_version.version - 1,
        )
    )
    prev_version = prev_result.scalar_one_or_none()
    if prev_version is None:
        logger.warning(
            "No previous version to rollback to for %s/%s (was at v%s)",
            target_type, target_key, active_version.version,
        )
        return None

    prev_version.is_active = True

    logger.info(
        "Rolled back prompt %s/%s from v%s to v%s",
        target_type, target_key, active_version.version, prev_version.version,
    )
    return prev_version


async def get_prompt_history(
    session: AsyncSession,
    target_type: str,
    target_key: str,
) -> list[dict]:
    """Get version history for a prompt target."""
    result = await session.execute(
        select(PromptVersion)
        .where(
            PromptVersion.target_type == target_type,
            PromptVersion.target_key == target_key,
        )
        .order_by(PromptVersion.version.desc())
    )
    versions = result.scalars().all()

    return [
        {
            "id": v.id,
            "version": v.version,
            "is_active": v.is_active,
            "experiment_id": v.experiment_id,
            "prompt_text": v.prompt_text,
            "diff_from_previous": v.diff_from_previous,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


async def compute_prompt_diff(old_text: str, new_text: str) -> str:
    """Compute a simple line-by-line diff between two prompt texts."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="previous",
        tofile="current",
    )
    return "".join(diff)
