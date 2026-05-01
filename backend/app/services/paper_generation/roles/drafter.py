"""Drafter role: composes manuscript from verified results and source spans.

Boundary: Every claim must map to a verified source span or result object.
           Cannot fabricate citations or elevate descriptive findings to causal
           claims unless the lock artifact permits that inference.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session

from app.models.claim_map import ClaimMap
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.paper_family import PaperFamily
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider

logger = logging.getLogger(__name__)

# Soft cap on claims per paper. The Verifier sends ALL claims in one
# LLM prompt; with 50 claims (production paper apep_28011bda) the
# prompt becomes too large and verification silently no-ops. 25 is
# comfortable for a single Verifier call (~6K tokens of claims YAML).
_MAX_CLAIMS_PER_PAPER = 25

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

DRAFT_SYSTEM_PROMPT = """\
You are the Drafter, responsible for composing a complete academic manuscript \
from verified results and source evidence. You write in LaTeX.

HARD BOUNDARIES:
- Every empirical claim MUST reference a specific result object or source span.
- You CANNOT fabricate citations to papers that do not exist.
- You CANNOT elevate descriptive findings to causal claims UNLESS the lock \
  artifact's identification strategy explicitly permits causal inference.
- You MUST follow the venue style indicated by the family's venue_ladder.
- All tables and figures must reference verified result objects.
"""

DRAFT_USER_PROMPT = """\
Compose a complete LaTeX manuscript for paper {paper_id}.

Locked research design:
{lock_yaml}

Protocol type: {protocol_type}
Permitted inference level: {inference_level}

Result manifest (analysis outputs):
{result_manifest}

Source manifest (data sources used):
{source_manifest}

Target venue style: {venue_style}

Family description: {family_description}

REGISTERED SOURCE CARDS (the ONLY valid source_ref values when
source_type="source_span"):
{registered_source_ids}

REGISTERED RESULT OBJECTS (the ONLY valid source_ref values when
source_type="result_object"):
{registered_result_object_names}

Write the COMPLETE manuscript with these sections:
1. Introduction (research question, contribution, roadmap)
2. Literature Review (position paper relative to existing work)
3. Methodology (identification strategy from the lock artifact)
4. Data (describe sources with Tier classification)
5. Results (present findings referencing specific result objects)
6. Discussion (interpret findings within lock artifact constraints)
7. Conclusion (policy implications, limitations)

For EACH central claim, include a comment indicating the evidence source:
  %% CLAIM: <claim_text> | SOURCE: <source_card_id or result_object_name>

CRITICAL — claim source linkage (production papers consistently fail
review when this is wrong):
- Each claim's ``source_ref`` MUST be either:
    - a SourceCard ID copied verbatim from REGISTERED SOURCE CARDS above
      (when source_type="source_span"), or
    - a result-object key copied verbatim from REGISTERED RESULT OBJECTS
      (when source_type="result_object").
- Do NOT invent source IDs (e.g. "29 CFR § 1607.4(d)" or
  "Griggs v. Duke Power"). If a claim genuinely needs a source not in
  the registered list, narrow the claim or drop it; do not paper over
  the gap with a free-text reference.
- Doctrinal/legal claims that cite specific authorities are fine in the
  manuscript prose — but the corresponding ClaimMap entry's
  ``source_ref`` must still resolve to a registered source card or
  result object.

CRITICAL — claim_type vs source TIER pairing (production paper
apep_3ddffa34 failed L2 with 14 tier_violations of this exact form):
- Empirical and doctrinal claims are CENTRAL — they carry the paper's
  argumentative weight. They MUST be anchored by a Tier A or Tier B
  source from the listing above.
- Tier C sources (incident logs, popular-press archives, opinion
  columns) can ONLY anchor:
    - claim_type="descriptive" (background context, scoping)
    - claim_type="theoretical" (illustrative example, not evidence)
    - claim_type="historical" (event-occurrence reporting)
- If you have a strong empirical claim that you can only support
  with a Tier C source, REWRITE it as descriptive or omit it. Do
  NOT pair empirical/doctrinal with Tier C — the L2 reviewer will
  fire CRITICAL tier_violation and the paper will fail.
- Use a MIX of claim_types where the evidence supports it: an all-
  empirical paper is suspicious. Background facts, framework
  descriptions, and event reporting should typically be descriptive
  or historical.

CRITICAL — claim_type vs source_type pairing (production paper
apep_5bd06118 was killed by the Verifier with 11 of 25 claims
failing because empirical claims were anchored to data sources
that don't actually contain the empirical finding):
- ``claim_type="empirical"`` claims state STATISTICAL FINDINGS that
  emerge from data analysis (e.g. "treatment increased disclosure
  by 23%", "pre-treatment trends are parallel", "the coefficient is
  significant at p<0.05"). These MUST use ``source_type="result_object"``
  and a ``source_ref`` from REGISTERED RESULT OBJECTS — not from
  REGISTERED SOURCE CARDS. The data source contains raw filings; the
  Analyst's result_objects contain the statistical findings derived
  from those filings.
- If your paper's protocol is empirical_causal but no result objects
  are registered (the Analyst stage produced no quantitative output),
  REWRITE empirical claims as descriptive ("The AIID database
  contains X incidents") or doctrinal ("The EU AI Act mandates Y").
  Do not assert findings the paper hasn't actually computed.
- ``claim_type="descriptive"`` / ``"doctrinal"`` claims state FACTS
  that exist in the source itself (e.g. "the EU AI Act mandates
  incident reporting", "the AIID database documents 1,200+ incidents").
  These use ``source_type="source_span"`` with a ``source_ref`` from
  REGISTERED SOURCE CARDS — the source's own text supports the claim
  directly.
- ``claim_type="theoretical"`` claims describe frameworks or
  predictions that don't require source verification. They can use
  ``source_type="source_span"`` if anchoring to a citing work.
- Bad pairings to avoid (the Verifier will fail every one):
    - "Pre-treatment trends are parallel" + source_type="source_span"
      + source_ref="edgar"   ← the EDGAR filings don't say this; an
      Analyst statistical test does
    - "The coefficient on incident exposure is 0.34" +
      source_type="source_span" + source_ref="aiid"   ← AIID is the
      raw incident database; the coefficient comes from regression
    - "AI systems mediate consequential decisions" +
      source_type="source_span" + source_ref="aiid"   ← AIID is
      specific incidents, not a general claim about AI's prevalence
      (this should be descriptive + cited from openalex literature
      review)

Return JSON:
{{
  "manuscript_latex": "<the full LaTeX document>",
  "claims": [
    {{
      "claim_text": "string",
      "claim_type": "empirical|descriptive|doctrinal|theoretical|historical",
      "source_type": "result_object|source_span",
      "source_ref": "string (MUST be from the registered lists above)",
      "section": "string (which section contains this claim)"
    }}
  ],
  "bibliography_entries": [
    {{
      "key": "string (bibtex key)",
      "type": "article|book|report|dataset",
      "title": "string",
      "authors": "string",
      "year": "string",
      "source": "string (journal/publisher)"
    }}
  ]
}}

No markdown wrapper, no commentary outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def compose_manuscript(
    paper_id: str,
    result_manifest: dict[str, Any] | None = None,
    source_manifest: dict[str, Any] | None = None,
    provider: LLMProvider | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Compose the full manuscript.

    Internally manages DB sessions in three phases (read → LLM → write)
    so we never hold a connection across the long manuscript-generation
    LLM call (max_tokens=32768; can take 1-3 min).

    The ``session`` parameter is kept for back-compat but ignored —
    every DB phase opens its own short-lived session.

    1. Load lock artifact, family info (short session)
    2. Generate LaTeX manuscript via LLM (no session held)
    3. Persist ClaimMap entries + funnel_stage update (short session)
    """
    del session  # explicitly ignored

    # ── Phase 1: reads (short-lived session) ─────────────────────────
    async with async_session() as s:
        paper = await _load_paper(s, paper_id)
        lock = await _load_active_lock(s, paper_id)
        if lock is None:
            raise ValueError(
                f"No active lock for paper '{paper_id}'. "
                "Design must be locked before drafting."
            )
        family = await _load_family(s, paper.family_id) if paper.family_id else None
        # Copy out values we need
        lock_yaml = lock.lock_yaml
        protocol_type = lock.lock_protocol_type
        inference_level = _determine_inference_level(protocol_type)
        venue_style = "general academic"
        if family and family.venue_ladder:
            try:
                venue_data = json.loads(family.venue_ladder)
                flagship = venue_data.get("flagship", [])
                if flagship:
                    venue_style = f"targeting {flagship[0]} style"
            except (json.JSONDecodeError, TypeError):
                pass
        family_description = family.description if family else "AI governance research"

        # Load registered SourceCard IDs so the prompt can present them
        # as the closed set of valid source_ref values. Production paper
        # apep_703f59f7 had 21/25 claims "soft-linked" because the LLM
        # invented source references like "29 CFR § 1607.4(d)" that
        # weren't in the registry. PR #51 added the closed-set listing.
        #
        # Production paper apep_3ddffa34 (run 25202085464) then revealed
        # the next gap: the Drafter ignored source TIER when picking a
        # source for empirical claims. 8/25 claims were anchored to a
        # Tier C source ("OECD AI Incidents Monitor"), generating 14
        # CRITICAL ``tier_violation`` issues at L2 because Tier C
        # sources cannot anchor central (empirical/doctrinal) claims.
        #
        # PR #55 groups sources by tier so the Drafter sees the tier
        # constraint structurally. Tier A/B sources are the ONLY valid
        # anchors for empirical/doctrinal claims; Tier C is for
        # auxiliary/descriptive only.
        from app.models.source_card import SourceCard

        sc_result = await s.execute(
            select(SourceCard.id, SourceCard.name, SourceCard.tier).where(
                SourceCard.active.is_(True)
            )
        )
        sources_by_tier: dict[str, list[str]] = {"A": [], "B": [], "C": []}
        for row in sc_result.all():
            tier = (row[2] or "C").upper()
            sources_by_tier.setdefault(tier, []).append(f"  - {row[0]} ({row[1]})")

        def _format_tier(letter: str) -> str:
            entries = sources_by_tier.get(letter, [])
            return "\n".join(entries) if entries else f"  (no Tier {letter} sources registered)"

        registered_source_ids_str = (
            "TIER A — primary, audited; SUITABLE for empirical/doctrinal:\n"
            f"{_format_tier('A')}\n"
            "\nTIER B — high-quality secondary; SUITABLE for empirical/doctrinal:\n"
            f"{_format_tier('B')}\n"
            "\nTIER C — auxiliary/contextual; ONLY for descriptive or "
            "supporting claims (NEVER as the anchor of an empirical or "
            "doctrinal claim — that's a CRITICAL tier_violation at review):\n"
            f"{_format_tier('C')}"
        )

    # ── Phase 2: LLM call (no session held) ──────────────────────────
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        from app.config import settings

        model = settings.claude_opus_model

    # Extract result-object names from the manifest so the prompt can
    # show them as a closed set just like source IDs.
    if result_manifest and isinstance(result_manifest.get("result_objects"), dict):
        ro_names = list(result_manifest["result_objects"].keys())
    else:
        ro_names = []
    registered_result_object_names_str = (
        "\n".join(f"  - {n}" for n in ro_names)
        if ro_names
        else "  (no result objects registered yet)"
    )

    prompt = DRAFT_USER_PROMPT.format(
        paper_id=paper_id,
        lock_yaml=lock_yaml,
        protocol_type=protocol_type,
        inference_level=inference_level,
        result_manifest=(
            json.dumps(result_manifest, indent=2)
            if result_manifest
            else "(no results yet)"
        ),
        source_manifest=(
            json.dumps(source_manifest, indent=2)
            if source_manifest
            else "(no manifest)"
        ),
        venue_style=venue_style,
        family_description=family_description,
        registered_source_ids=registered_source_ids_str,
        registered_result_object_names=registered_result_object_names_str,
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.5,
        max_tokens=32768,
    )

    parsed = _parse_json_object(response)
    manuscript_latex = parsed.get("manuscript_latex", "")
    claims_raw = parsed.get("claims", [])
    bibliography = parsed.get("bibliography_entries", [])

    # Cap claims to keep the Verifier's downstream LLM call manageable.
    # Production paper apep_28011bda generated 50 claims and the
    # Verifier choked on the resulting prompt, leaving all 50 pending.
    # 25 is comfortable for one Verifier call (~6K tokens of claims
    # YAML) and still produces a substantive provenance footprint.
    if len(claims_raw) > _MAX_CLAIMS_PER_PAPER:
        logger.info(
            "Drafter capped claim count: %d → %d for paper %s",
            len(claims_raw),
            _MAX_CLAIMS_PER_PAPER,
            paper_id,
        )
        # Prefer empirical / doctrinal claims over theoretical ones —
        # they're the ones provenance attribution matters most for.
        priority = {"empirical": 0, "doctrinal": 1, "descriptive": 2}
        claims_raw = sorted(
            claims_raw,
            key=lambda c: priority.get(c.get("claim_type", ""), 99),
        )[:_MAX_CLAIMS_PER_PAPER]

    # ── Phase 3: writes (short-lived session, fresh connection) ──────
    claim_map_entries: list[dict[str, Any]] = []
    async with async_session() as s:
        # Load registered source-card IDs so we can validate the LLM's
        # source_ref. Without validation, the Drafter's INSERT into
        # claim_maps blows up with a ForeignKeyViolationError when
        # the LLM picks bogus IDs (production run #25144089527).
        #
        # Soft validation: if source_ref isn't a registered ID, store
        # the raw value in source_span_ref instead of NULL'ing out the
        # whole linkage. PR #31's strict NULL'ing destroyed Paper 2's
        # provenance (48/50 claims with NULL source) when the LLM
        # picked concept names like "Brussels Effect" instead of
        # source_card IDs. Preserving the raw value lets the Verifier
        # flag it as un-validated rather than the system pretending
        # the claim has no evidence at all.
        from app.models.source_card import SourceCard

        sc_result = await s.execute(
            select(SourceCard.id).where(SourceCard.active.is_(True))
        )
        registered_source_ids = {row[0] for row in sc_result.all()}

        # Track miscategorised claims for the warning log. Production
        # paper apep_5bd06118 had 11 of 25 claims fail Verifier because
        # ``empirical`` claims were anchored to data sources rather
        # than result_objects (the source's text didn't contain the
        # statistical finding the claim asserted).
        empirical_with_source_span = 0
        for claim_data in claims_raw:
            source_type = claim_data.get("source_type", "")
            source_ref = claim_data.get("source_ref", "")
            claim_type = claim_data.get("claim_type", "descriptive")

            # Diagnostic: empirical/doctrinal claims with source_span
            # source_type are suspect — they assert statistical
            # findings that the raw source can't verify. Don't reject;
            # just count and log the rate. The Verifier will still
            # downstream-fail these, but this log gives the operator
            # an early signal that the Drafter is mis-anchoring.
            if (
                claim_type.lower() == "empirical"
                and source_type == "source_span"
            ):
                empirical_with_source_span += 1

            valid_source_card_id: str | None = None
            soft_source_span_ref: str | None = None
            if source_type == "source_span":
                if source_ref in registered_source_ids:
                    # Hard match — set FK
                    valid_source_card_id = source_ref
                elif source_ref:
                    # Soft match — preserve in source_span_ref so the
                    # Verifier can see what the LLM intended, even
                    # though it didn't pick a registered ID.
                    soft_source_span_ref = json.dumps(
                        {"name": source_ref, "registered": False}
                    )

            claim_map = ClaimMap(
                paper_id=paper_id,
                claim_text=claim_data.get("claim_text", ""),
                claim_type=claim_type,
                source_card_id=valid_source_card_id,
                source_span_ref=soft_source_span_ref,
                result_object_ref=(
                    json.dumps({"name": source_ref})
                    if source_type == "result_object"
                    else None
                ),
                verification_status="pending",
            )
            s.add(claim_map)
            claim_map_entries.append(
                {
                    "claim_text": claim_data.get("claim_text", ""),
                    "claim_type": claim_data.get("claim_type", "descriptive"),
                    "source_type": source_type,
                    "source_ref": source_ref,
                    "section": claim_data.get("section", ""),
                }
            )
        # Extract the manuscript title from the LaTeX so the paper
        # record shows it instead of the placeholder "Generating...".
        # Production paper apep_faf874ae completed but its title still
        # showed the placeholder.
        title = _extract_latex_title(manuscript_latex)

        paper = await _load_paper(s, paper_id)
        paper.funnel_stage = "drafting"
        if title:
            paper.title = title
        # PR #58: persist the manuscript content so it survives Render
        # redeploys (the disk file at paper_tex_path can be wiped).
        # Stored on Paper rather than PaperPackage because PaperPackage
        # is created later by the Packager — by then we want the
        # manuscript to already be queryable.
        if manuscript_latex:
            paper.manuscript_latex = manuscript_latex
        s.add(paper)
        await s.commit()

    logger.info(
        "Drafter composed manuscript for paper %s (%d claims, %d bibliography entries)",
        paper_id,
        len(claim_map_entries),
        len(bibliography),
    )
    # Diagnostic warning: production paper apep_5bd06118 had 11/25
    # claims fail Verifier because ``empirical`` claims were anchored
    # to data sources (source_span). Surface this rate so operators
    # can see when the Drafter's prompt-following is weak.
    if empirical_with_source_span > 0:
        logger.warning(
            "Drafter: paper %s has %d/%d empirical claims anchored to "
            "source_span instead of result_object — these will likely "
            "fail Verifier (the raw source doesn't contain the "
            "statistical finding the claim asserts).",
            paper_id,
            empirical_with_source_span,
            len(claim_map_entries),
        )

    return {
        "manuscript_latex": manuscript_latex,
        "claims": claim_map_entries,
        "bibliography": bibliography,
        "inference_level": inference_level,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_paper(session: AsyncSession, paper_id: str) -> Paper:
    stmt = select(Paper).where(Paper.id == paper_id)
    result = await session.execute(stmt)
    paper = result.scalar_one_or_none()
    if paper is None:
        raise ValueError(f"Paper '{paper_id}' not found.")
    return paper


async def _load_active_lock(
    session: AsyncSession, paper_id: str
) -> LockArtifact | None:
    stmt = (
        select(LockArtifact)
        .where(
            LockArtifact.paper_id == paper_id,
            LockArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _load_family(session: AsyncSession, family_id: str) -> PaperFamily | None:
    stmt = select(PaperFamily).where(PaperFamily.id == family_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _determine_inference_level(protocol_type: str) -> str:
    """Map protocol type to permitted inference level."""
    causal_protocols = {"empirical_causal"}
    descriptive_protocols = {"measurement_text", "synthesis_bibliometric"}
    process_protocols = {"process_tracing", "comparative_historical"}
    theory_protocols = {"theory"}
    doctrinal_protocols = {"doctrinal"}

    if protocol_type in causal_protocols:
        return "causal (with valid identification strategy)"
    elif protocol_type in descriptive_protocols:
        return "descriptive only (no causal claims)"
    elif protocol_type in process_protocols:
        return "mechanistic (within-case causal with evidence thresholds)"
    elif protocol_type in theory_protocols:
        return "theoretical (formal model implications)"
    elif protocol_type in doctrinal_protocols:
        return "interpretive (legal analysis, not causal)"
    else:
        return "descriptive only (unknown protocol, conservative default)"


def _parse_json_object(response: str) -> dict:
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse manuscript JSON from LLM response")
        return {
            "manuscript_latex": "",
            "claims": [],
            "bibliography_entries": [],
        }


def _extract_latex_title(manuscript_latex: str) -> str | None:
    """Pull the title out of a LaTeX manuscript via ``\\title{...}``.

    Returns the title text (stripped of LaTeX braces and surrounding
    whitespace) or None if no title block is found / the title is
    empty. Used by ``compose_manuscript`` to update the ``papers.title``
    column from its ``"Generating..."`` placeholder once the manuscript
    is ready.
    """
    if not manuscript_latex:
        return None
    import re

    # Match \title{...} allowing for nested braces (one level deep is
    # plenty for typical academic titles like \title{Foo: \emph{Bar}}).
    match = re.search(
        r"\\title\{((?:[^{}]|\{[^{}]*\})*)\}", manuscript_latex, re.DOTALL
    )
    if not match:
        return None
    title = match.group(1).strip()
    # Strip simple LaTeX commands that academic titles often include
    # (e.g. \emph{...} -> ...). Conservative — a more sophisticated
    # de-LaTeX is overkill for a DB column.
    title = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", title)
    title = title.strip()
    # Cap at the column length (papers.title is String(512)).
    return title[:512] if title else None
