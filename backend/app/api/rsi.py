"""API routes for the RSI (Recursive Self-Improvement) tier system.

Exposes ~40 endpoints covering all RSI tiers: experiment management, prompt
versioning, role/review prompt optimisation, policy calibration, family
config tuning, drift thresholds, judge calibration, layer/role architecture,
family/taxonomy discovery, improvement targeting, and the meta pipeline.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

# ── Service imports ──────────────────────────────────────────────────────────
from app.services.rsi.experiment_manager import (
    activate_experiment as svc_activate_experiment,
    rollback_experiment as svc_rollback_experiment,
    get_active_experiments as svc_get_active_experiments,
    get_experiment as svc_get_experiment,
    get_rsi_dashboard as svc_get_rsi_dashboard,
)
from app.services.rsi.prompt_registry import (
    get_prompt_history as svc_get_prompt_history,
    activate_prompt_version as svc_activate_prompt_version,
    rollback_prompt as svc_rollback_prompt,
)
from app.services.rsi.role_prompt_optimizer import (
    analyze_role_failures as svc_analyze_role_failures,
    propose_prompt_patch as svc_propose_prompt_patch,
    evaluate_prompt_patch as svc_evaluate_prompt_patch,
    get_role_prompt_status as svc_get_role_prompt_status,
)
from app.services.rsi.review_prompt_sharpener import (
    analyze_layer_accuracy as svc_analyze_layer_accuracy,
    propose_review_prompt_patch as svc_propose_review_prompt_patch,
    get_all_layer_accuracy as svc_get_all_layer_accuracy,
)
from app.services.rsi.policy_calibrator import (
    correlate_dimensions_with_outcomes as svc_correlate_dimensions_with_outcomes,
    propose_dimension_reweighting as svc_propose_dimension_reweighting,
    get_calibration_status as svc_get_calibration_status,
)
from app.services.rsi.family_config_optimizer import (
    compute_family_health as svc_compute_family_health,
    propose_config_changes as svc_propose_config_changes,
    get_all_family_health as svc_get_all_family_health,
)
from app.services.rsi.drift_tuner import (
    compute_gate_metrics as svc_compute_gate_metrics,
    propose_threshold_adjustment as svc_propose_threshold_adjustment,
    apply_threshold as svc_apply_threshold,
    get_threshold_history as svc_get_threshold_history,
)
from app.services.rsi.judge_calibrator_rsi import (
    correlate_rankings_with_outcomes as svc_correlate_rankings_with_outcomes,
    propose_judge_adjustment as svc_propose_judge_adjustment,
    get_judge_calibration_overview as svc_get_judge_calibration_overview,
)
from app.services.rsi.layer_architect import (
    audit_layer_effectiveness as svc_audit_layer_effectiveness,
    propose_layer_bypass as svc_propose_layer_bypass,
    enable_shadow_layer as svc_enable_shadow_layer,
    evaluate_shadow_results as svc_evaluate_shadow_results,
    get_layer_config as svc_get_layer_config,
)
from app.services.rsi.role_architect import (
    analyze_role_boundary_failures as svc_analyze_role_boundary_failures,
    propose_role_split as svc_propose_role_split,
    propose_role_merge as svc_propose_role_merge,
    get_role_architecture as svc_get_role_architecture,
)
from app.services.rsi.family_discoverer import (
    cluster_killed_ideas as svc_cluster_killed_ideas,
    propose_new_family as svc_propose_new_family,
    approve_family_proposal as svc_approve_family_proposal,
    get_family_proposals as svc_get_family_proposals,
)
from app.services.rsi.taxonomy_expander import (
    cluster_other_failures as svc_cluster_other_failures,
    propose_new_failure_type as svc_propose_new_failure_type,
    approve_failure_type as svc_approve_failure_type,
    get_taxonomy_status as svc_get_taxonomy_status,
)
from app.services.rsi.improvement_targeter import (
    compute_cohort_deltas as svc_compute_cohort_deltas,
    identify_improvement_targets as svc_identify_improvement_targets,
    generate_improvement_summary as svc_generate_improvement_summary,
)
from app.services.rsi.meta_pipeline import (
    execute_meta_cycle as svc_execute_meta_cycle,
    get_meta_pipeline_runs as svc_get_meta_pipeline_runs,
    get_meta_pipeline_run as svc_get_meta_pipeline_run,
)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Request body models
# ═══════════════════════════════════════════════════════════════════════════════

class RollbackExperimentRequest(BaseModel):
    reason: str = Field("", max_length=5000)


class ApplyThresholdRequest(BaseModel):
    new_threshold: float = Field(..., ge=0.0, le=1.0)
    family_id: str = Field(..., max_length=100)


class ProposeLayerBypassRequest(BaseModel):
    family_id: str = Field(..., max_length=100)
    condition: str = Field(..., max_length=2000)


class EnableShadowLayerRequest(BaseModel):
    family_id: str = Field(..., max_length=100)


class ProposeRoleMergeRequest(BaseModel):
    role_a: str = Field(..., max_length=200)
    role_b: str = Field(..., max_length=200)


class ProposeNewFamilyRequest(BaseModel):
    cluster_id: Optional[str] = Field(None, max_length=100)
    cluster_label: Optional[str] = Field(None, max_length=300)
    paper_ids: list[str] = Field(default_factory=list, max_length=500)
    rationale: Optional[str] = Field(None, max_length=5000)


class ProposeNewFailureTypeRequest(BaseModel):
    cluster_id: Optional[str] = Field(None, max_length=100)
    cluster_label: Optional[str] = Field(None, max_length=300)
    example_ids: list[str] = Field(default_factory=list, max_length=500)
    rationale: Optional[str] = Field(None, max_length=5000)


# ═══════════════════════════════════════════════════════════════════════════════
# Core — Dashboard & Experiments
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/dashboard")
async def rsi_dashboard(db: AsyncSession = Depends(get_db)):
    """Return the top-level RSI dashboard: experiment counts by tier/status and recent gate logs."""
    return await svc_get_rsi_dashboard(db)


@router.get("/rsi/experiments")
async def list_experiments(
    tier: Optional[str] = Query(None, description="Filter by RSI tier (e.g. 1a, 2b)"),
    family_id: Optional[str] = Query(None, description="Filter by paper family"),
    status: Optional[str] = Query(None, description="Filter by experiment status"),
    db: AsyncSession = Depends(get_db),
):
    """List active/non-archived RSI experiments with optional filters."""
    return await svc_get_active_experiments(db, tier=tier, family_id=family_id)


@router.get("/rsi/experiments/{experiment_id}")
async def get_experiment(experiment_id: int, db: AsyncSession = Depends(get_db)):
    """Get full detail for a single RSI experiment."""
    result = await svc_get_experiment(db, experiment_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    return result


@router.post("/rsi/experiments/{experiment_id}/activate")
@limiter.limit("20/hour")
async def activate_experiment(request: Request, experiment_id: int, db: AsyncSession = Depends(get_db)):
    """Activate a proposed/shadow experiment."""
    try:
        experiment = await svc_activate_experiment(db, experiment_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to activate experiment %d", experiment_id)
        raise HTTPException(status_code=500, detail="Failed to activate experiment")
    return {"id": experiment.id, "status": experiment.status}


@router.post("/rsi/experiments/{experiment_id}/rollback")
@limiter.limit("20/hour")
async def rollback_experiment(
    request: Request,
    experiment_id: int,
    body: RollbackExperimentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Roll back an active experiment with a reason."""
    try:
        experiment = await svc_rollback_experiment(db, experiment_id, reason=body.reason)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to rollback experiment %d", experiment_id)
        raise HTTPException(status_code=500, detail="Failed to rollback experiment")
    return {"id": experiment.id, "status": experiment.status}


# ═══════════════════════════════════════════════════════════════════════════════
# Prompts — Versioning & Rollback
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/prompts/{target_type}/{target_key}/history")
async def get_prompt_history(
    target_type: str,
    target_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the full version history for a prompt target (e.g. role_prompt/scout)."""
    return await svc_get_prompt_history(db, target_type, target_key)


@router.post("/rsi/prompts/{version_id}/activate")
@limiter.limit("20/hour")
async def activate_prompt_version(request: Request, version_id: int, db: AsyncSession = Depends(get_db)):
    """Activate a specific prompt version, deactivating all others for that target."""
    try:
        version = await svc_activate_prompt_version(db, version_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to activate prompt version %d", version_id)
        raise HTTPException(status_code=500, detail="Failed to activate prompt version")
    return {
        "id": version.id,
        "version": version.version,
        "is_active": version.is_active,
        "target_type": version.target_type,
        "target_key": version.target_key,
    }


@router.post("/rsi/prompts/{target_type}/{target_key}/rollback")
@limiter.limit("20/hour")
async def rollback_prompt(
    request: Request,
    target_type: str,
    target_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Rollback: deactivate the current prompt version and reactivate the previous one."""
    try:
        result = await svc_rollback_prompt(db, target_type, target_key)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to rollback prompt %s/%s", target_type, target_key)
        raise HTTPException(status_code=500, detail="Failed to rollback prompt")
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active prompt to roll back for {target_type}/{target_key}",
        )
    return {
        "id": result.id,
        "version": result.version,
        "is_active": result.is_active,
        "target_type": result.target_type,
        "target_key": result.target_key,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 1a — Role Prompt Optimisation
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier1a/status")
async def tier1a_status(db: AsyncSession = Depends(get_db)):
    """Get prompt-optimisation status for all pipeline roles."""
    return await svc_get_role_prompt_status(db)


@router.post("/rsi/tier1a/analyze/{role_name}")
@limiter.limit("10/hour")
async def tier1a_analyze(
    request: Request,
    role_name: str,
    family_id: Optional[str] = Query(None, description="Scope analysis to a family"),
    lookback_days: int = Query(90, ge=1, le=365, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
):
    """Analyze failure patterns for a specific pipeline role."""
    try:
        return await svc_analyze_role_failures(
            db, role_name, family_id=family_id, lookback_days=lookback_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rsi/tier1a/propose/{role_name}")
@limiter.limit("10/hour")
async def tier1a_propose(request: Request, role_name: str, db: AsyncSession = Depends(get_db)):
    """Propose a prompt patch for a role based on recent failure analysis."""
    try:
        analysis = await svc_analyze_role_failures(db, role_name)
        result = await svc_propose_prompt_patch(db, role_name, failure_analysis=analysis)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose prompt patch for role %s", role_name)
        raise HTTPException(status_code=500, detail="Failed to propose prompt patch")
    return result


@router.post("/rsi/tier1a/evaluate/{experiment_id}")
@limiter.limit("10/hour")
async def tier1a_evaluate(request: Request, experiment_id: int, db: AsyncSession = Depends(get_db)):
    """Evaluate a prompt-patch experiment by comparing pre/post failure rates."""
    try:
        result = await svc_evaluate_prompt_patch(db, experiment_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to evaluate prompt patch for experiment %d", experiment_id)
        raise HTTPException(status_code=500, detail="Failed to evaluate prompt patch")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 1b — Review Prompt Sharpening
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier1b/accuracy")
async def tier1b_all_accuracy(db: AsyncSession = Depends(get_db)):
    """Get accuracy metrics across all review layers."""
    return await svc_get_all_layer_accuracy(db)


@router.get("/rsi/tier1b/accuracy/{layer}")
async def tier1b_layer_accuracy(layer: str, db: AsyncSession = Depends(get_db)):
    """Get detailed accuracy breakdown for a single review layer."""
    try:
        return await svc_analyze_layer_accuracy(db, layer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rsi/tier1b/propose/{layer}")
@limiter.limit("10/hour")
async def tier1b_propose(request: Request, layer: str, db: AsyncSession = Depends(get_db)):
    """Propose a prompt patch for a review layer to reduce false positives/negatives."""
    try:
        result = await svc_propose_review_prompt_patch(db, layer)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose review prompt patch for layer %s", layer)
        raise HTTPException(status_code=500, detail="Failed to propose review prompt patch")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 1c — Policy Calibration
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier1c/correlations")
async def tier1c_correlations(
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Correlate review dimensions with submission outcomes."""
    return await svc_correlate_dimensions_with_outcomes(db, family_id=family_id)


@router.get("/rsi/tier1c/status")
async def tier1c_status(db: AsyncSession = Depends(get_db)):
    """Get the current policy calibration status."""
    return await svc_get_calibration_status(db)


@router.post("/rsi/tier1c/propose-reweighting")
@limiter.limit("10/hour")
async def tier1c_propose_reweighting(request: Request, db: AsyncSession = Depends(get_db)):
    """Propose dimension reweighting based on outcome correlations."""
    try:
        result = await svc_propose_dimension_reweighting(db)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose dimension reweighting")
        raise HTTPException(status_code=500, detail="Failed to propose dimension reweighting")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 2a — Family Config Optimisation
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier2a/health")
async def tier2a_all_health(db: AsyncSession = Depends(get_db)):
    """Get health summaries for all active paper families."""
    return await svc_get_all_family_health(db)


@router.get("/rsi/tier2a/health/{family_id}")
async def tier2a_family_health(family_id: str, db: AsyncSession = Depends(get_db)):
    """Compute a comprehensive health report for a single paper family."""
    return await svc_compute_family_health(db, family_id)


@router.post("/rsi/tier2a/propose/{family_id}")
@limiter.limit("10/hour")
async def tier2a_propose(request: Request, family_id: str, db: AsyncSession = Depends(get_db)):
    """Propose configuration changes for a family based on its health report."""
    try:
        health = await svc_compute_family_health(db, family_id)
        result = await svc_propose_config_changes(db, family_id, health_report=health)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose config changes for family %s", family_id)
        raise HTTPException(status_code=500, detail="Failed to propose config changes")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 2b — Drift Threshold Tuning
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier2b/metrics")
async def tier2b_metrics(
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Compute gate pass/fail metrics for drift detection."""
    return await svc_compute_gate_metrics(db, family_id=family_id)


@router.get("/rsi/tier2b/history")
async def tier2b_history(
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Get the history of threshold adjustments."""
    return await svc_get_threshold_history(db, family_id=family_id)


@router.post("/rsi/tier2b/propose")
@limiter.limit("10/hour")
async def tier2b_propose(
    request: Request,
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Propose a new drift threshold based on current gate metrics."""
    try:
        result = await svc_propose_threshold_adjustment(db, family_id=family_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose threshold adjustment")
        raise HTTPException(status_code=500, detail="Failed to propose threshold adjustment")
    return result


@router.post("/rsi/tier2b/apply")
@limiter.limit("20/hour")
async def tier2b_apply(request: Request, body: ApplyThresholdRequest, db: AsyncSession = Depends(get_db)):
    """Apply a new drift threshold value."""
    try:
        result = await svc_apply_threshold(
            db, new_threshold=body.new_threshold, family_id=body.family_id,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to apply threshold")
        raise HTTPException(status_code=500, detail="Failed to apply threshold")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 2c — Judge Calibration
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier2c/overview")
async def tier2c_overview(db: AsyncSession = Depends(get_db)):
    """Get the overall judge-calibration overview across families."""
    return await svc_get_judge_calibration_overview(db)


@router.get("/rsi/tier2c/correlation/{family_id}")
async def tier2c_correlation(family_id: str, db: AsyncSession = Depends(get_db)):
    """Correlate tournament rankings with real-world outcomes for a family."""
    return await svc_correlate_rankings_with_outcomes(db, family_id)


@router.post("/rsi/tier2c/propose/{family_id}")
@limiter.limit("10/hour")
async def tier2c_propose(request: Request, family_id: str, db: AsyncSession = Depends(get_db)):
    """Propose a judge-calibration adjustment for a family."""
    try:
        result = await svc_propose_judge_adjustment(db, family_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose judge adjustment for family %s", family_id)
        raise HTTPException(status_code=500, detail="Failed to propose judge adjustment")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 3a — Layer Architecture
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier3a/effectiveness")
async def tier3a_effectiveness(
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Audit per-layer effectiveness: pass rates, false-positive rates, value-add."""
    return await svc_audit_layer_effectiveness(db, family_id=family_id)


@router.get("/rsi/tier3a/config")
async def tier3a_config(
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Get the current layer configuration (bypass rules, shadow layers, etc.)."""
    return await svc_get_layer_config(db, family_id=family_id)


@router.post("/rsi/tier3a/propose-bypass/{layer}")
@limiter.limit("10/hour")
async def tier3a_propose_bypass(
    request: Request,
    layer: str,
    body: ProposeLayerBypassRequest,
    db: AsyncSession = Depends(get_db),
):
    """Propose bypassing a review layer under a specified condition."""
    try:
        result = await svc_propose_layer_bypass(
            db, layer, family_id=body.family_id, condition=body.condition,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose layer bypass for %s", layer)
        raise HTTPException(status_code=500, detail="Failed to propose layer bypass")
    return result


@router.post("/rsi/tier3a/enable-shadow/{layer}")
@limiter.limit("10/hour")
async def tier3a_enable_shadow(
    request: Request,
    layer: str,
    body: EnableShadowLayerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enable shadow mode for a review layer so it runs but does not gate."""
    try:
        result = await svc_enable_shadow_layer(db, layer, family_id=body.family_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to enable shadow layer %s", layer)
        raise HTTPException(status_code=500, detail="Failed to enable shadow layer")
    return result


@router.post("/rsi/tier3a/evaluate-shadow/{config_id}")
@limiter.limit("10/hour")
async def tier3a_evaluate_shadow(request: Request, config_id: int, db: AsyncSession = Depends(get_db)):
    """Evaluate collected shadow-layer results to decide on promotion or removal."""
    try:
        result = await svc_evaluate_shadow_results(db, config_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to evaluate shadow results for config %d", config_id)
        raise HTTPException(status_code=500, detail="Failed to evaluate shadow results")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 3b — Role Architecture
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier3b/boundary-failures")
async def tier3b_boundary_failures(db: AsyncSession = Depends(get_db)):
    """Analyze failures that fall on role boundaries (unclear ownership)."""
    return await svc_analyze_role_boundary_failures(db)


@router.get("/rsi/tier3b/architecture")
async def tier3b_architecture(
    family_id: Optional[str] = Query(None, description="Scope to a family"),
    db: AsyncSession = Depends(get_db),
):
    """Get the current role architecture map."""
    return await svc_get_role_architecture(db, family_id=family_id)


@router.post("/rsi/tier3b/propose-split/{role_name}")
@limiter.limit("10/hour")
async def tier3b_propose_split(request: Request, role_name: str, db: AsyncSession = Depends(get_db)):
    """Propose splitting a role into sub-roles based on boundary-failure analysis."""
    try:
        result = await svc_propose_role_split(db, role_name)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose role split for %s", role_name)
        raise HTTPException(status_code=500, detail="Failed to propose role split")
    return result


@router.post("/rsi/tier3b/propose-merge")
@limiter.limit("10/hour")
async def tier3b_propose_merge(
    request: Request,
    body: ProposeRoleMergeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Propose merging two roles that have significant overlap."""
    try:
        result = await svc_propose_role_merge(db, role_a=body.role_a, role_b=body.role_b)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose role merge")
        raise HTTPException(status_code=500, detail="Failed to propose role merge")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 3c — Family Discovery
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier3c/clusters")
async def tier3c_clusters(db: AsyncSession = Depends(get_db)):
    """Cluster killed ideas to discover potential new paper families."""
    return await svc_cluster_killed_ideas(db)


@router.get("/rsi/tier3c/proposals")
async def tier3c_proposals(db: AsyncSession = Depends(get_db)):
    """List all pending and approved new-family proposals."""
    return await svc_get_family_proposals(db)


@router.post("/rsi/tier3c/propose-family")
@limiter.limit("10/hour")
async def tier3c_propose_family(
    request: Request,
    body: ProposeNewFamilyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Propose a new paper family from cluster data."""
    try:
        result = await svc_propose_new_family(
            db,
            cluster_id=body.cluster_id,
            cluster_label=body.cluster_label,
            paper_ids=body.paper_ids,
            rationale=body.rationale,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose new family")
        raise HTTPException(status_code=500, detail="Failed to propose new family")
    return result


@router.post("/rsi/tier3c/approve/{proposal_id}")
@limiter.limit("20/hour")
async def tier3c_approve(request: Request, proposal_id: int, db: AsyncSession = Depends(get_db)):
    """Approve a pending new-family proposal, creating the family."""
    try:
        result = await svc_approve_family_proposal(db, proposal_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to approve family proposal %d", proposal_id)
        raise HTTPException(status_code=500, detail="Failed to approve family proposal")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 4a — Taxonomy Expansion
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier4a/clusters")
async def tier4a_clusters(db: AsyncSession = Depends(get_db)):
    """Cluster 'other' failures to discover potential new failure types."""
    return await svc_cluster_other_failures(db)


@router.get("/rsi/tier4a/status")
async def tier4a_status(db: AsyncSession = Depends(get_db)):
    """Get the current taxonomy expansion status and pending proposals."""
    return await svc_get_taxonomy_status(db)


@router.post("/rsi/tier4a/propose")
@limiter.limit("10/hour")
async def tier4a_propose(
    request: Request,
    body: ProposeNewFailureTypeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Propose adding a new failure type to the taxonomy."""
    try:
        result = await svc_propose_new_failure_type(
            db,
            cluster_id=body.cluster_id,
            cluster_label=body.cluster_label,
            example_ids=body.example_ids,
            rationale=body.rationale,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to propose new failure type")
        raise HTTPException(status_code=500, detail="Failed to propose new failure type")
    return result


@router.post("/rsi/tier4a/approve/{proposal_id}")
@limiter.limit("20/hour")
async def tier4a_approve(request: Request, proposal_id: int, db: AsyncSession = Depends(get_db)):
    """Approve a pending failure-type proposal, adding it to the taxonomy."""
    try:
        result = await svc_approve_failure_type(db, proposal_id)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Failed to approve failure type %d", proposal_id)
        raise HTTPException(status_code=500, detail="Failed to approve failure type")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 4b — Improvement Targeting
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/rsi/tier4b/cohort-deltas")
async def tier4b_cohort_deltas(db: AsyncSession = Depends(get_db)):
    """Compute cohort-over-cohort metric deltas to detect improvement or regression."""
    return await svc_compute_cohort_deltas(db)


@router.get("/rsi/tier4b/targets")
async def tier4b_targets(db: AsyncSession = Depends(get_db)):
    """Identify the highest-leverage improvement targets across tiers."""
    return await svc_identify_improvement_targets(db)


@router.get("/rsi/tier4b/summary")
async def tier4b_summary(db: AsyncSession = Depends(get_db)):
    """Generate a human-readable improvement summary."""
    return await svc_generate_improvement_summary(db)


# ═══════════════════════════════════════════════════════════════════════════════
# Tier 4c — Meta Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/rsi/tier4c/start-cycle")
@limiter.limit("2/hour")
async def tier4c_start_cycle(request: Request, db: AsyncSession = Depends(get_db)):
    """Execute a full meta-pipeline cycle (analyze, propose, evaluate across all tiers)."""
    try:
        result = await svc_execute_meta_cycle(db)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        logger.exception("Meta pipeline cycle failed")
        raise HTTPException(status_code=500, detail="Meta pipeline cycle failed")
    return result


@router.get("/rsi/tier4c/runs")
async def tier4c_runs(db: AsyncSession = Depends(get_db)):
    """List all meta-pipeline runs."""
    return await svc_get_meta_pipeline_runs(db)


@router.get("/rsi/tier4c/runs/{run_id}")
async def tier4c_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Get detail for a single meta-pipeline run."""
    result = await svc_get_meta_pipeline_run(db, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Meta-pipeline run {run_id} not found")
    return result
