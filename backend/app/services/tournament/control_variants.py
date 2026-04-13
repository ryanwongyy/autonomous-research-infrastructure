"""Generates control variant metadata for judge calibration.

In production, these would be actual corrupted papers.
In dev, they are descriptions of what would be corrupted.

Each corruption type maps to a specific ``lock_protocol_type`` (family
protocol) and contains a list of corruption entries.  A calibration run
picks corruptions appropriate to the family's protocol so the judge is
tested on domain-relevant failure modes.
"""

from __future__ import annotations

CORRUPTION_TYPES: dict[str, list[dict]] = {
    # ---- empirical / causal ----
    "empirical_causal": [
        {
            "name": "bad_controls",
            "description": "Post-treatment controls added, biasing estimates",
            "severity": "fatal",
        },
        {
            "name": "broken_event_study",
            "description": "Event window includes confounding policy change",
            "severity": "fatal",
        },
        {
            "name": "unsupported_causal",
            "description": "Causal language used for descriptive findings",
            "severity": "major",
        },
        {
            "name": "p_hacked",
            "description": "Specification search until significance found",
            "severity": "fatal",
        },
        {
            "name": "data_leakage",
            "description": "Outcome variable leaks into treatment assignment",
            "severity": "fatal",
        },
    ],
    # ---- measurement / text ----
    "measurement_text": [
        {
            "name": "unvalidated_coding",
            "description": "No inter-rater reliability reported",
            "severity": "major",
        },
        {
            "name": "cherry_picked_corpus",
            "description": "Corpus boundary chosen to support thesis",
            "severity": "major",
        },
        {
            "name": "uninterpretable_topics",
            "description": "Topic model output not validated by domain expert",
            "severity": "major",
        },
        {
            "name": "dropped_validation",
            "description": "Validation checks present in pre-reg but absent from final paper",
            "severity": "fatal",
        },
    ],
    # ---- doctrinal / legal ----
    "doctrinal": [
        {
            "name": "missing_authorities",
            "description": "Key binding precedents omitted from analysis",
            "severity": "fatal",
        },
        {
            "name": "misquoted_statute",
            "description": "Statutory text altered to support argument",
            "severity": "fatal",
        },
        {
            "name": "jurisdiction_error",
            "description": "Wrong jurisdiction's law applied without acknowledgement",
            "severity": "fatal",
        },
        {
            "name": "superseded_case",
            "description": "Relies on overruled or superseded authority",
            "severity": "major",
        },
    ],
    # ---- theory / formal ----
    "theory": [
        {
            "name": "proof_gap",
            "description": "Key lemma stated without proof and not cited",
            "severity": "fatal",
        },
        {
            "name": "assumption_slippage",
            "description": "Stronger assumption quietly introduced mid-proof",
            "severity": "major",
        },
        {
            "name": "notation_inconsistency",
            "description": "Same symbol reused for different concepts across sections",
            "severity": "minor",
        },
        {
            "name": "trivial_extension",
            "description": "Main result is a direct corollary of existing work, presented as novel",
            "severity": "major",
        },
    ],
    # ---- synthesis / bibliometric ----
    "synthesis_bibliometric": [
        {
            "name": "hidden_selection_bias",
            "description": "Systematic exclusion of studies contradicting thesis",
            "severity": "fatal",
        },
        {
            "name": "unreproducible_search",
            "description": "Search strategy too vague to reproduce",
            "severity": "major",
        },
        {
            "name": "publication_bias_ignored",
            "description": "No funnel plot or trim-and-fill despite heterogeneity",
            "severity": "major",
        },
        {
            "name": "vote_counting",
            "description": "Narrative count of significant results replaces proper effect-size synthesis",
            "severity": "major",
        },
    ],
}


def get_corruptions_for_protocol(protocol_type: str) -> list[dict]:
    """Return the list of corruption templates matching a family's protocol.

    Falls back to ``empirical_causal`` if the protocol is not recognised.
    """
    return CORRUPTION_TYPES.get(protocol_type, CORRUPTION_TYPES["empirical_causal"])


def build_variant_description(
    base_paper_title: str,
    corruption: dict,
    variant_index: int,
) -> dict:
    """Build a metadata dict describing a single corrupted variant.

    In dev mode these are *descriptions* of what would be corrupted, not
    actual corrupted paper texts.
    """
    return {
        "variant_index": variant_index,
        "base_paper_title": base_paper_title,
        "corruption_name": corruption["name"],
        "corruption_description": corruption["description"],
        "severity": corruption.get("severity", "major"),
        "expected_judge_action": (
            "must_lose" if corruption.get("severity") == "fatal" else "should_be_penalised"
        ),
    }
