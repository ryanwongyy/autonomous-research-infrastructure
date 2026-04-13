"""5-Layer Review Pipeline

New architecture (Phase 4):
  L1: Structural integrity (no LLM)
  L2: Provenance verification (no LLM, uses claim_verifier)
  L3: Method review (non-Claude model, GPT-4o)
  L4: Adversarial red-team review (multi-model: Claude + GPT-4o)
  L5: Human escalation (no LLM, generates report)

Entry point: orchestrator.run_review_pipeline()
"""

from app.services.review_pipeline.orchestrator import run_review_pipeline

__all__ = ["run_review_pipeline"]
