"""
Seed data for all 11 APE paper families.

Run directly:
    python -m seeds.families

Or via the seed runner:
    python -m seeds.run_seeds
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure the backend directory is on sys.path so app imports resolve.
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy import select  # noqa: E402

from app.database import async_session, init_db  # noqa: E402
from app.models.paper_family import PaperFamily  # noqa: E402


# ---------------------------------------------------------------------------
# Family definitions
# ---------------------------------------------------------------------------

FAMILIES: list[dict] = [
    # ------------------------------------------------------------------ F1
    {
        "id": "F1",
        "name": "Causal evaluation of governance instruments",
        "short_name": "causal_governance",
        "description": (
            "Empirical papers that estimate the causal effect of governance "
            "instruments -- laws, rules, enforcement actions, procurement "
            "policies -- on measurable outcomes. Identification strategy is "
            "the centrepiece; the paper must convince readers that the "
            "estimated effect is not confounded."
        ),
        "lock_protocol_type": "empirical_causal",
        "canonical_questions": json.dumps([
            "Does a new AI disclosure rule actually change corporate behaviour?",
            "What is the causal effect of procurement AI clauses on vendor compliance?",
            "Do enforcement actions deter future violations in the regulated population?",
            "How does a mandatory impact-assessment law affect deployment timelines?",
        ]),
        "accepted_methods": json.dumps([
            "Difference-in-differences (DiD)",
            "Synthetic control",
            "Comparative interrupted time series",
            "Regression discontinuity (RD)",
            "Instrumental variables (IV)",
            "Event studies",
            "Matched panels",
        ]),
        "public_data_sources": json.dumps([
            "Laws and rules (legislative text, regulatory final rules)",
            "EDGAR filings",
            "Procurement records",
            "Enforcement actions",
            "Public incidents",
            "Public economic outcomes",
        ]),
        "novelty_threshold": (
            "A credible identification strategy applied to a governance question "
            "that matters beyond a single jurisdiction. The design must be "
            "convincing on its own terms, not merely novel in topic."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "General social-science venues (top economics, political science, management journals)",
            ],
            "elite_field": [
                "Governance journals",
                "Policy journals",
                "Empirical legal studies journals",
                "Research Policy",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Identification memo",
            "Falsification tests",
            "Treatment-timing audit",
            "Spillover memo",
            "Causal-language audit",
        ]),
        "fatal_failures": json.dumps([
            "Policy endogeneity waved away",
            "Post-treatment controls included",
            "Weak or poorly measured outcomes",
            "Unstable treatment coding",
        ]),
        "elite_ceiling": (
            "Credible design plus a question that matters outside one jurisdiction."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "identification_strength",
                    "weight": 0.30,
                    "description": "Is the causal identification strategy credible and well-defended?",
                },
                {
                    "name": "data_quality",
                    "weight": 0.20,
                    "description": "Are data sources public, well-documented, and sufficient for the design?",
                },
                {
                    "name": "robustness_checks",
                    "weight": 0.20,
                    "description": "Are falsification tests, sensitivity analyses, and spillover checks present and convincing?",
                },
                {
                    "name": "question_significance",
                    "weight": 0.15,
                    "description": "Does the governance question matter beyond the specific jurisdiction studied?",
                },
                {
                    "name": "causal_language_discipline",
                    "weight": 0.15,
                    "description": "Does the paper avoid overclaiming causality where the design cannot support it?",
                },
            ],
            "punished_mainly_for": [
                "Waving away policy endogeneity",
                "Including post-treatment controls",
                "Weak or poorly measured outcome variables",
                "Unstable or subjective treatment coding",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F2
    {
        "id": "F2",
        "name": "Measurement and governance-architecture papers",
        "short_name": "measurement_governance",
        "description": (
            "Papers that build, validate, and deploy measures of governance "
            "constructs -- indices, coding schemes, latent variables -- that "
            "the field can reuse. The contribution is the measure itself and "
            "its demonstrated construct validity."
        ),
        "lock_protocol_type": "measurement_text",
        "canonical_questions": json.dumps([
            "How should we measure the stringency of national AI regulation?",
            "Can a validated coding scheme capture the breadth of AI-ethics commitments in corporate filings?",
            "What latent dimensions underlie the variation in AI governance frameworks?",
            "How invariant is a governance-architecture index across jurisdictions and time?",
        ]),
        "accepted_methods": json.dumps([
            "Corpus assembly",
            "Hand-coding with validation",
            "LLM-assisted coding with validation",
            "Latent measurement models",
            "Inter-coder reliability analysis",
            "Measurement invariance testing",
        ]),
        "public_data_sources": json.dumps([
            "Statutes",
            "Guidance documents",
            "Consultation materials",
            "Filings",
            "Procurement texts",
            "Incident records",
        ]),
        "novelty_threshold": (
            "The paper changes how the field operationalises a core AI-governance "
            "construct. A new index is not enough; the measure must be shown to "
            "be superior to existing alternatives or to capture a dimension "
            "previously unmeasured."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Occasionally when the measure settles an important question (top general venues)",
            ],
            "elite_field": [
                "Elite field journals (governance, policy, management, political science methods)",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Construct-validity memo",
            "Adversarial recoding",
            "Release documentation",
            "Sensitivity to coding choices",
        ]),
        "fatal_failures": json.dumps([
            "Subjective coding without validation",
            "Dataset release without theory",
            "Indices whose components do all the work",
        ]),
        "elite_ceiling": (
            "Paper changes how the field operationalises AI governance."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "construct_validity",
                    "weight": 0.30,
                    "description": "Is the measure theoretically grounded and empirically validated?",
                },
                {
                    "name": "replicability_and_release",
                    "weight": 0.25,
                    "description": "Is the coding scheme documented well enough for independent replication? Is the dataset releasable?",
                },
                {
                    "name": "measurement_robustness",
                    "weight": 0.20,
                    "description": "Is the measure robust to alternative coding choices and across contexts?",
                },
                {
                    "name": "theoretical_contribution",
                    "weight": 0.15,
                    "description": "Does the measure capture a governance dimension that existing indices miss?",
                },
                {
                    "name": "inter_coder_reliability",
                    "weight": 0.10,
                    "description": "Are inter-coder reliability statistics reported and at acceptable thresholds?",
                },
            ],
            "punished_mainly_for": [
                "Subjective coding without validation",
                "Releasing a dataset without a theoretical contribution",
                "Indices where a single component drives all the variation",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F3
    {
        "id": "F3",
        "name": "Computational text-as-data and disclosure mining",
        "short_name": "text_as_data",
        "description": (
            "Papers that apply computational text-analysis methods -- NLP, "
            "supervised classification, embeddings, topic models -- to "
            "governance corpora. Validated textual measures tied to "
            "institutional theory are the target contribution."
        ),
        "lock_protocol_type": "measurement_text",
        "canonical_questions": json.dumps([
            "What topics dominate AI-governance consultations, and how do they evolve?",
            "Can supervised classifiers reliably identify substantive AI-risk disclosures in corporate filings?",
            "How do citation networks among regulatory documents reveal diffusion patterns?",
            "Do transparency reports contain measurably different content from marketing materials?",
        ]),
        "accepted_methods": json.dumps([
            "Supervised classification",
            "Embedding-based retrieval",
            "Citation-network analysis",
            "Document linkage",
            "Structured topic models with validation",
        ]),
        "public_data_sources": json.dumps([
            "Regulations",
            "Consultations",
            "Hearings",
            "Filings",
            "Model cards",
            "System cards",
            "Transparency reports",
        ]),
        "novelty_threshold": (
            "Validated textual measures tied to institutional theory. "
            "Pure NLP engineering without a governance theory is insufficient."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Governance journals",
                "Policy journals",
                "Political-methods journals",
                "Management journals",
                "Research-policy journals",
            ],
            "elite_field": [
                "Governance journals",
                "Policy journals",
                "Political-methods journals",
                "Management journals",
                "Research-policy journals",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Annotation audit",
            "Out-of-sample validation",
            "Prompt/version lock if LLM coding",
            "Label-stability tests across models",
        ]),
        "fatal_failures": json.dumps([
            "Unvalidated LLM coding",
            "Uninterpretable topic output",
            "Rhetoric treated as conduct",
        ]),
        "elite_ceiling": (
            "Validated textual measures tied to institutional theory."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "validation_rigour",
                    "weight": 0.30,
                    "description": "Are text-analysis outputs validated against human judgement and robust across models?",
                },
                {
                    "name": "institutional_grounding",
                    "weight": 0.25,
                    "description": "Are textual measures connected to governance theory, not just NLP output?",
                },
                {
                    "name": "out_of_sample_performance",
                    "weight": 0.20,
                    "description": "Does the classifier or measure generalise beyond the training corpus?",
                },
                {
                    "name": "reproducibility",
                    "weight": 0.15,
                    "description": "Are prompts, model versions, and annotation protocols fully locked and documented?",
                },
                {
                    "name": "rhetoric_vs_conduct",
                    "weight": 0.10,
                    "description": "Does the paper distinguish between what documents say and what institutions do?",
                },
            ],
            "punished_mainly_for": [
                "Unvalidated LLM coding passed off as measurement",
                "Topic-model output without interpretability or validation",
                "Treating rhetorical claims in documents as evidence of conduct",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F4
    {
        "id": "F4",
        "name": "Comparative and historical regulatory-administrative governance",
        "short_name": "comparative_historical",
        "description": (
            "Papers that compare governance institutions across jurisdictions "
            "or trace their development over time. The contribution is a new "
            "explanation of institutional divergence or convergence grounded "
            "in structured comparison and historical evidence."
        ),
        "lock_protocol_type": "comparative_historical",
        "canonical_questions": json.dumps([
            "Why did the EU and US diverge on AI-risk classification frameworks?",
            "How did national administrative traditions shape AI governance architectures?",
            "What sequences of policy adoption characterise early versus late regulators?",
            "Can nested comparison of agencies explain variation in enforcement intensity?",
        ]),
        "accepted_methods": json.dumps([
            "Structured focused comparison",
            "Historical institutional analysis",
            "Sequence analysis",
            "Nested comparison",
        ]),
        "public_data_sources": json.dumps([
            "Policy corpora",
            "Legislative histories",
            "Agency guidance",
            "Official consultations",
            "Archival government records",
        ]),
        "novelty_threshold": (
            "A new explanation of institutional divergence or convergence "
            "that goes beyond descriptive comparison."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Governance journals",
                "Public-administration journals",
                "Comparative-politics journals",
                "Selected law venues",
            ],
            "elite_field": [
                "Governance journals",
                "Public-administration journals",
                "Comparative-politics journals",
                "Selected law venues",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Jurisdiction-selection memo",
            "Rival-explanations table",
            "Timeline validation",
            "Source-balance audit",
        ]),
        "fatal_failures": json.dumps([
            "Cherry-picked countries",
            "Shallow comparison without structured method",
            "Overclaiming harmonisation",
        ]),
        "elite_ceiling": (
            "New explanation of institutional divergence or convergence."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "case_selection_rigour",
                    "weight": 0.25,
                    "description": "Is the jurisdiction selection theoretically motivated and transparently justified?",
                },
                {
                    "name": "structured_comparison",
                    "weight": 0.25,
                    "description": "Does the comparison follow a structured method rather than ad-hoc narrative?",
                },
                {
                    "name": "rival_explanations",
                    "weight": 0.20,
                    "description": "Are alternative explanations explicitly considered and tested?",
                },
                {
                    "name": "historical_depth",
                    "weight": 0.15,
                    "description": "Is the historical evidence deep enough to support the institutional claims?",
                },
                {
                    "name": "source_balance",
                    "weight": 0.15,
                    "description": "Are sources balanced across jurisdictions, not dominated by one country's archives?",
                },
            ],
            "punished_mainly_for": [
                "Cherry-picked country selection",
                "Shallow or impressionistic comparison",
                "Overclaiming harmonisation from surface similarity",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F5
    {
        "id": "F5",
        "name": "Legal-doctrinal and enforcement analysis",
        "short_name": "legal_doctrinal",
        "description": (
            "Papers that perform rigorous doctrinal synthesis, statutory "
            "interpretation, or case-law analysis relevant to AI governance. "
            "The contribution must matter to courts, agencies, or serious "
            "legal scholars -- not merely restate the law."
        ),
        "lock_protocol_type": "doctrinal",
        "canonical_questions": json.dumps([
            "How should existing product-liability doctrine apply to autonomous-system harms?",
            "What statutory basis supports (or undermines) agency authority over AI deployment?",
            "How do enforcement decisions construct the meaning of algorithmic fairness requirements?",
            "What comparative-law lessons apply to cross-border AI liability?",
        ]),
        "accepted_methods": json.dumps([
            "Doctrinal synthesis",
            "Structured statutory interpretation",
            "Case-law analysis",
            "Comparative law",
        ]),
        "public_data_sources": json.dumps([
            "Statutes",
            "Regulations",
            "Cases",
            "Agency orders",
            "Enforcement decisions",
            "Official guidance",
        ]),
        "novelty_threshold": (
            "Paper would matter to courts, agencies, or serious legal scholars. "
            "It must advance the doctrinal conversation, not merely summarise it."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Top general law reviews",
            ],
            "elite_field": [
                "Elite specialty law journals",
                "Peer-reviewed legal journals",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Source-hierarchy table",
            "Contrary-authority search",
            "Quote verification",
            "Jurisdiction memo",
            "Administrability test",
        ]),
        "fatal_failures": json.dumps([
            "Advocacy memo posing as scholarship",
            "Missing contrary authorities",
            "No institutional consequence analysis",
        ]),
        "elite_ceiling": (
            "Paper would matter to courts, agencies, or serious legal scholars."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "doctrinal_rigour",
                    "weight": 0.30,
                    "description": "Is the legal analysis thorough, correctly sourced, and hierarchically ordered?",
                },
                {
                    "name": "contrary_authority",
                    "weight": 0.25,
                    "description": "Does the paper engage with contrary authorities and opposing doctrinal positions?",
                },
                {
                    "name": "institutional_consequence",
                    "weight": 0.20,
                    "description": "Does the analysis trace through to institutional consequences, not just legal theory?",
                },
                {
                    "name": "scholarly_contribution",
                    "weight": 0.15,
                    "description": "Does the paper advance the doctrinal conversation beyond summary or restatement?",
                },
                {
                    "name": "administrability",
                    "weight": 0.10,
                    "description": "Are proposed legal rules or interpretations administrable by real institutions?",
                },
            ],
            "punished_mainly_for": [
                "Advocacy posing as scholarship",
                "Missing contrary authorities or opposing positions",
                "No analysis of institutional consequences",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F6
    {
        "id": "F6",
        "name": "Corporate governance and disclosure",
        "short_name": "corporate_disclosure",
        "description": (
            "Papers that study how corporations govern and disclose their AI "
            "activities -- through filings, proxy statements, transparency "
            "reports, model cards, and system cards. The paper must be about "
            "governance accountability, not PR language."
        ),
        "lock_protocol_type": "empirical_causal",
        "canonical_questions": json.dumps([
            "Do AI-governance disclosures in SEC filings predict actual internal practices?",
            "How do board AI-oversight structures relate to deployment outcomes?",
            "What drives variation in the substance of model cards across firms?",
            "Does mandatory AI-risk disclosure change corporate governance behaviour?",
        ]),
        "accepted_methods": json.dumps([
            "Panel disclosure analysis",
            "Event studies",
            "Hand-coded governance variables",
            "Comparative disclosure mapping",
        ]),
        "public_data_sources": json.dumps([
            "SEC filings",
            "Proxy statements",
            "Annual reports",
            "Public transparency reports",
            "System cards",
            "Model cards",
            "Entity registries",
        ]),
        "novelty_threshold": (
            "Paper about governance accountability, not PR language. "
            "Must distinguish between what firms say and what they do."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Elite management journals",
                "Elite accounting journals",
                "Elite organisation journals",
                "Research-policy journals",
            ],
            "elite_field": [
                "Elite management journals",
                "Elite accounting journals",
                "Elite organisation journals",
                "Research-policy journals",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Disclosure-to-practice caution audit",
            "Event-window sensitivity",
            "Sample-construction audit",
            "Boilerplate filter",
        ]),
        "fatal_failures": json.dumps([
            "Equating disclosure with internal practice",
            "Selective sample construction",
            "Trivial keyword measures",
        ]),
        "elite_ceiling": (
            "Paper about governance accountability, not PR language."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "disclosure_practice_distinction",
                    "weight": 0.30,
                    "description": "Does the paper carefully distinguish between disclosure content and actual governance practice?",
                },
                {
                    "name": "sample_construction",
                    "weight": 0.25,
                    "description": "Is the sample transparently constructed, not cherry-picked, and representative?",
                },
                {
                    "name": "measurement_quality",
                    "weight": 0.20,
                    "description": "Are governance variables hand-coded or validated, not simple keyword counts?",
                },
                {
                    "name": "causal_design",
                    "weight": 0.15,
                    "description": "If causal claims are made, is the identification strategy credible?",
                },
                {
                    "name": "boilerplate_awareness",
                    "weight": 0.10,
                    "description": "Does the paper filter or account for boilerplate and performative disclosure?",
                },
            ],
            "punished_mainly_for": [
                "Equating disclosure language with internal governance practice",
                "Selective or unrepresentative sample construction",
                "Trivial keyword-count measures treated as governance variables",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F7
    {
        "id": "F7",
        "name": "Public procurement and state capacity",
        "short_name": "procurement_state",
        "description": (
            "Papers that study AI-related public procurement as a governance "
            "mechanism -- contracts, tenders, vendor selection, and compliance. "
            "The contribution frames procurement as governance, not as "
            "bookkeeping."
        ),
        "lock_protocol_type": "empirical_causal",
        "canonical_questions": json.dumps([
            "How do AI clauses in public contracts affect vendor compliance and performance?",
            "What procurement network structures emerge around government AI acquisitions?",
            "Does procurement centralisation improve or hinder AI governance outcomes?",
            "How do RFP requirements for AI transparency translate into delivered systems?",
        ]),
        "accepted_methods": json.dumps([
            "Contract-level analysis",
            "Procurement network analysis",
            "Causal analysis where timing permits",
            "Comparative procurement-law analysis",
            "RFP text mining",
        ]),
        "public_data_sources": json.dumps([
            "Contract notices",
            "Awards",
            "Budgets",
            "Procurement portals",
            "Tender databases",
        ]),
        "novelty_threshold": (
            "Procurement as governance, not procurement as bookkeeping. "
            "The paper must connect procurement data to governance theory."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Elite public-administration journals",
                "Governance journals",
                "Research-policy journals",
            ],
            "elite_field": [
                "Elite public-administration journals",
                "Governance journals",
                "Research-policy journals",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Notice-versus-award distinction",
            "Vendor/entity resolution",
            "Amendment audit",
            "Missingness audit",
        ]),
        "fatal_failures": json.dumps([
            "Confusing expressions of interest with contracts",
            "Ignoring framework agreements",
            "Weak performance measures",
        ]),
        "elite_ceiling": (
            "Procurement as governance, not procurement as bookkeeping."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "governance_framing",
                    "weight": 0.25,
                    "description": "Is procurement analysed as a governance mechanism, not mere data bookkeeping?",
                },
                {
                    "name": "data_accuracy",
                    "weight": 0.25,
                    "description": "Are procurement records correctly distinguished (notices vs awards) and entities resolved?",
                },
                {
                    "name": "causal_or_descriptive_quality",
                    "weight": 0.20,
                    "description": "If causal claims are made, is the timing-based design credible? If descriptive, is coverage comprehensive?",
                },
                {
                    "name": "completeness_audit",
                    "weight": 0.15,
                    "description": "Are framework agreements, amendments, and missingness accounted for?",
                },
                {
                    "name": "performance_measurement",
                    "weight": 0.15,
                    "description": "Are outcome measures meaningful, not just contract counts?",
                },
            ],
            "punished_mainly_for": [
                "Confusing expressions of interest with awarded contracts",
                "Ignoring framework agreements in procurement analysis",
                "Using weak or trivial performance measures",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F8
    {
        "id": "F8",
        "name": "Incident, enforcement, and institutional learning / process tracing",
        "short_name": "incident_process_tracing",
        "description": (
            "Papers that use process tracing, nested case studies, and "
            "event-history methods to uncover how institutions learn (or fail "
            "to learn) from AI incidents, enforcement actions, and crises. "
            "The paper must uncover institutional learning mechanisms, not "
            "just recount events."
        ),
        "lock_protocol_type": "process_tracing",
        "canonical_questions": json.dumps([
            "How did a specific AI incident reshape agency enforcement priorities?",
            "What institutional learning mechanisms operated (or failed) after a high-profile AI failure?",
            "Do patterns in incident-response sequences reveal systematic governance weaknesses?",
            "How do nested case studies of enforcement actions illuminate regulatory capacity?",
        ]),
        "accepted_methods": json.dumps([
            "Process tracing",
            "Nested case studies",
            "Event-history modelling",
            "Carefully bounded qualitative comparison",
        ]),
        "public_data_sources": json.dumps([
            "Incident databases",
            "Official investigations",
            "Hearings",
            "Court records",
            "Agency actions",
            "Public statements",
            "Press (only as corroboration, not primary evidence)",
        ]),
        "novelty_threshold": (
            "Paper uncovers institutional learning mechanisms. "
            "Recounting what happened is not enough; the paper must explain "
            "how and why institutions responded as they did."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Elite governance journals",
                "Business-and-politics journals",
                "Policy journals",
                "Law venues",
            ],
            "elite_field": [
                "Elite governance journals",
                "Business-and-politics journals",
                "Policy journals",
                "Law venues",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Chronology lock",
            "Triangulation threshold",
            "Alternative-mechanism tests",
            "Source-quality ladder",
        ]),
        "fatal_failures": json.dumps([
            "Anecdotalism",
            "Press-only evidentiary base",
            "Fame-biased case selection",
        ]),
        "elite_ceiling": (
            "Paper uncovers institutional learning mechanisms."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "process_tracing_rigour",
                    "weight": 0.30,
                    "description": "Is the causal-process tracing disciplined, with explicit tests of alternative mechanisms?",
                },
                {
                    "name": "evidence_quality",
                    "weight": 0.25,
                    "description": "Is evidence triangulated from multiple source types, not reliant on press accounts?",
                },
                {
                    "name": "case_selection",
                    "weight": 0.20,
                    "description": "Are cases selected for theoretical leverage, not fame or convenience?",
                },
                {
                    "name": "chronology_integrity",
                    "weight": 0.15,
                    "description": "Is the event chronology locked and verified, preventing post-hoc narrative fitting?",
                },
                {
                    "name": "institutional_mechanism",
                    "weight": 0.10,
                    "description": "Does the paper identify a genuine institutional-learning mechanism, not just recount events?",
                },
            ],
            "punished_mainly_for": [
                "Anecdotalism without systematic process tracing",
                "Relying on press reports as primary evidence",
                "Selecting cases based on fame rather than theoretical leverage",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F9
    {
        "id": "F9",
        "name": "International governance and regime-complex studies",
        "short_name": "international_regime",
        "description": (
            "Papers that study AI governance at the international level -- "
            "declarations, regime complexes, cross-border coordination, and "
            "institutional interactions. The contribution must be an IR "
            "contribution, not an annotated timeline of international events."
        ),
        "lock_protocol_type": "comparative_historical",
        "canonical_questions": json.dumps([
            "How does the AI governance regime complex structure state behaviour?",
            "What explains variation in national implementation of international AI commitments?",
            "How does text reuse across declarations reveal institutional influence?",
            "Do international AI governance networks exhibit power-law or polycentric structures?",
        ]),
        "accepted_methods": json.dumps([
            "Network analysis",
            "Instrument mapping",
            "Text reuse analysis",
            "Process tracing",
            "Comparative institutional analysis",
        ]),
        "public_data_sources": json.dumps([
            "International declarations",
            "Communiques",
            "National policy records",
            "Implementation documents",
            "Meeting records (where public)",
        ]),
        "novelty_threshold": (
            "An IR contribution, not an annotated timeline. "
            "The paper must engage with international-relations theory, "
            "not merely catalogue events."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Elite IR and global-governance journals",
                "Governance journals",
            ],
            "elite_field": [
                "Elite IR and global-governance journals",
                "Governance journals",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Actor and instrument resolution",
            "Version control for declarations",
            "Multilingual verification",
        ]),
        "fatal_failures": json.dumps([
            "Counting documents as influence",
            "Equating sign-on with compliance",
            "Ignoring institutional incentives",
        ]),
        "elite_ceiling": (
            "IR contribution, not annotated timeline."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "ir_theoretical_grounding",
                    "weight": 0.30,
                    "description": "Does the paper engage with IR theory, not just describe international events?",
                },
                {
                    "name": "actor_instrument_precision",
                    "weight": 0.25,
                    "description": "Are actors and instruments precisely identified and consistently resolved?",
                },
                {
                    "name": "compliance_vs_signalling",
                    "weight": 0.20,
                    "description": "Does the paper distinguish between sign-on, implementation, and compliance?",
                },
                {
                    "name": "multilingual_coverage",
                    "weight": 0.15,
                    "description": "Are non-English sources consulted where relevant?",
                },
                {
                    "name": "version_control",
                    "weight": 0.10,
                    "description": "Are evolving declarations tracked with version control, not treated as static?",
                },
            ],
            "punished_mainly_for": [
                "Counting document production as evidence of influence",
                "Equating political sign-on with compliance or implementation",
                "Ignoring the institutional incentives behind international positions",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F10
    {
        "id": "F10",
        "name": "Formal theory and institutional design",
        "short_name": "formal_theory",
        "description": (
            "Papers that use formal methods -- game theory, mechanism design, "
            "incomplete contracts, dynamic regulation models -- to study AI "
            "governance. Data discipline examples and institutional assumptions "
            "but is not hidden calibration. The theory must change how a real "
            "governance mechanism would be designed."
        ),
        "lock_protocol_type": "theory",
        "canonical_questions": json.dumps([
            "What is the optimal design of an AI audit mandate under incomplete contracts?",
            "How should a regulator set inspection intensity when firms can strategically invest in safety?",
            "What game-theoretic equilibria emerge in multi-regulator AI oversight?",
            "How does dynamic regulation interact with the pace of AI capability development?",
        ]),
        "accepted_methods": json.dumps([
            "Game theory",
            "Mechanism design",
            "Incomplete contracts",
            "Dynamic regulation models",
        ]),
        "public_data_sources": json.dumps([
            "Used to discipline examples and institutional assumptions, not as hidden calibration",
        ]),
        "novelty_threshold": (
            "Theory that changes how a real governance mechanism would be designed. "
            "A toy model is insufficient; the formal structure must speak to "
            "an identifiable governance lever."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Elite theory journals",
                "Law-and-economics journals",
                "Public-economics journals",
                "Management journals",
            ],
            "elite_field": [
                "Elite theory journals",
                "Law-and-economics journals",
                "Public-economics journals",
                "Management journals",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Proof audit",
            "Assumption audit",
            "Comparative statics sensitivity",
            "Institution-mapping memo",
        ]),
        "fatal_failures": json.dumps([
            "Toy models without governance relevance",
            "Hidden assumptions driving the result",
            "No governance lever identified",
        ]),
        "elite_ceiling": (
            "Theory that changes how a real governance mechanism would be designed."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "formal_correctness",
                    "weight": 0.25,
                    "description": "Are proofs correct and assumptions explicitly stated?",
                },
                {
                    "name": "governance_relevance",
                    "weight": 0.25,
                    "description": "Does the model speak to an identifiable real governance lever?",
                },
                {
                    "name": "assumption_transparency",
                    "weight": 0.20,
                    "description": "Are hidden assumptions identified and sensitivity to them reported?",
                },
                {
                    "name": "comparative_statics",
                    "weight": 0.15,
                    "description": "Are comparative statics meaningful and robust to perturbation?",
                },
                {
                    "name": "institutional_mapping",
                    "weight": 0.15,
                    "description": "Does the paper map formal objects to real institutions convincingly?",
                },
            ],
            "punished_mainly_for": [
                "Toy models with no connection to real governance mechanisms",
                "Hidden assumptions that drive the main result",
                "No identifiable governance lever or policy implication",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
    # ------------------------------------------------------------------ F11
    {
        "id": "F11",
        "name": "Systematic reviews, evidence syntheses, and bibliometrics",
        "short_name": "systematic_review",
        "description": (
            "Papers that conduct systematic reviews, evidence syntheses, "
            "evidence-gap mapping, or bibliometric network analysis of the "
            "AI-governance literature. The contribution is a canonical map "
            "of a rapidly growing field, not a superficial keyword review."
        ),
        "lock_protocol_type": "synthesis_bibliometric",
        "canonical_questions": json.dumps([
            "What does the causal-evidence base tell us about the effectiveness of AI transparency mandates?",
            "Where are the major evidence gaps in the AI-governance literature?",
            "How has the bibliometric structure of AI-governance research evolved?",
            "What methodological patterns characterise high-impact versus low-impact governance studies?",
        ]),
        "accepted_methods": json.dumps([
            "Registered search",
            "Inclusion/exclusion coding",
            "Evidence-gap maps",
            "Bibliometric network analysis",
        ]),
        "public_data_sources": json.dumps([
            "OpenAlex",
            "Crossref",
            "Public full texts",
            "Public working papers",
            "Lawful open repositories",
        ]),
        "novelty_threshold": (
            "Canonical map of a rapidly growing field. "
            "Must go beyond keyword counting to provide genuine synthesis logic."
        ),
        "venue_ladder": json.dumps({
            "flagship": [
                "Elite field journals",
                "Invited review venues",
            ],
            "elite_field": [
                "Elite field journals",
                "Invited review venues",
            ],
        }),
        "mandatory_checks": json.dumps([
            "Search reproducibility",
            "Screening audit",
            "Deduplication audit",
            "Coding reliability",
            "Database-bias memo",
        ]),
        "fatal_failures": json.dumps([
            "Superficial keyword review",
            "No synthesis logic",
            "Hidden selection bias",
        ]),
        "elite_ceiling": (
            "Canonical map of rapidly growing field."
        ),
        "review_rubric": json.dumps({
            "criteria": [
                {
                    "name": "search_reproducibility",
                    "weight": 0.25,
                    "description": "Is the search strategy fully documented and reproducible?",
                },
                {
                    "name": "synthesis_logic",
                    "weight": 0.25,
                    "description": "Does the paper provide genuine synthesis, not just a list of findings?",
                },
                {
                    "name": "screening_rigour",
                    "weight": 0.20,
                    "description": "Are inclusion/exclusion criteria clear, applied consistently, and audited?",
                },
                {
                    "name": "selection_bias_awareness",
                    "weight": 0.15,
                    "description": "Does the paper address database bias, language bias, and publication bias?",
                },
                {
                    "name": "coding_reliability",
                    "weight": 0.15,
                    "description": "Is evidence coding reliable across coders and transparent in documentation?",
                },
            ],
            "punished_mainly_for": [
                "Superficial keyword review without synthesis logic",
                "No genuine synthesis -- just a list of papers",
                "Hidden selection bias in search or screening",
            ],
        }),
        "max_portfolio_share": 0.33,
        "active": True,
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------


async def seed_families() -> None:
    """Insert the 11 paper families if they do not already exist."""
    await init_db()

    async with async_session() as session:
        # Check whether families are already seeded.
        result = await session.execute(
            select(PaperFamily).limit(1)
        )
        existing = result.scalars().first()
        if existing is not None:
            print(f"[seeds/families] Families already seeded (found {existing.id}). Skipping.")
            return

        for fam in FAMILIES:
            family = PaperFamily(**fam)
            session.add(family)

        await session.commit()
        print(f"[seeds/families] Inserted {len(FAMILIES)} paper families.")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(seed_families())
