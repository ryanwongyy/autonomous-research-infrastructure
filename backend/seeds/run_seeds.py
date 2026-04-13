"""
Run all seed functions.

Usage:
    cd backend
    python -m seeds.run_seeds
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the backend directory is on sys.path so app imports resolve.
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from seeds.families import seed_families  # noqa: E402
from seeds.source_cards import seed_source_cards  # noqa: E402


async def run_all_seeds() -> None:
    """Execute every seed function in dependency order."""
    print("[seeds] Starting seed run...")

    await seed_families()
    await seed_source_cards()

    print("[seeds] All seeds complete.")


if __name__ == "__main__":
    asyncio.run(run_all_seeds())
