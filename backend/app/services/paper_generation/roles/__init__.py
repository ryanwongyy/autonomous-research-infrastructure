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

from app.services.paper_generation.roles.scout import generate_ideas, screen_idea
from app.services.paper_generation.roles.designer import create_research_design, lock_design
from app.services.paper_generation.roles.data_steward import build_source_manifest, fetch_and_snapshot
from app.services.paper_generation.roles.analyst import generate_analysis_code, execute_analysis
from app.services.paper_generation.roles.drafter import compose_manuscript
from app.services.paper_generation.roles.verifier import verify_manuscript
from app.services.paper_generation.roles.packager import build_package

__all__ = [
    "generate_ideas",
    "screen_idea",
    "create_research_design",
    "lock_design",
    "build_source_manifest",
    "fetch_and_snapshot",
    "generate_analysis_code",
    "execute_analysis",
    "compose_manuscript",
    "verify_manuscript",
    "build_package",
]
