"""Bounded role modules for the AI-governance paper generation pipeline.

Each role has clearly defined read/write boundaries:

1. Scout      - proposes ideas (read-only on source cards, no drafting)
2. Designer   - creates lock artifacts (output is immutable after lock)
3. DataSteward - builds source manifests, fetches data (no analysis)
4. Analyst    - generates/runs analysis code (no design modification)
5. Drafter    - composes manuscript (every claim must map to evidence)
6. Verifier   - cross-checks claims (read-only, flags violations)
7. Packager   - assembles final package (computes hashes, no content edits)
"""

from app.services.paper_generation.roles.analyst import execute_analysis, generate_analysis_code
from app.services.paper_generation.roles.data_steward import (
    build_source_manifest,
    fetch_and_snapshot,
)
from app.services.paper_generation.roles.designer import create_research_design, lock_design
from app.services.paper_generation.roles.drafter import compose_manuscript
from app.services.paper_generation.roles.packager import build_package
from app.services.paper_generation.roles.scout import generate_ideas, screen_idea
from app.services.paper_generation.roles.verifier import verify_manuscript

__all__ = [
    "build_package",
    "build_source_manifest",
    "compose_manuscript",
    "create_research_design",
    "execute_analysis",
    "fetch_and_snapshot",
    "generate_analysis_code",
    "generate_ideas",
    "lock_design",
    "screen_idea",
    "verify_manuscript",
]
