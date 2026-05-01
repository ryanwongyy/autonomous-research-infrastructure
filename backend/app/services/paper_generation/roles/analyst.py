"""Analyst role: writes analysis code and extracts results.

Boundary: Reads the locked design and source snapshots.
           Cannot modify the research design or raw data.
           Generated code is hashed before and after execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.lock_artifact import LockArtifact
from app.models.paper import Paper
from app.models.source_snapshot import SourceSnapshot
from app.services.llm.provider import LLMProvider
from app.services.llm.router import get_generation_provider
from app.services.provenance.hasher import hash_content

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """\
You are the Analyst, responsible for writing executable analysis code that \
implements the locked research design exactly. You read the frozen design and \
source data schemas, then produce a self-contained Python script.

HARD BOUNDARIES:
- You may READ the lock artifact and source snapshots.
- You WRITE analysis code (Python) and a requirements file.
- You CANNOT modify the research design or the raw data files.
- The code must be deterministic where possible (set random seeds).
"""

ANALYSIS_USER_PROMPT = """\
Generate analysis code for paper {paper_id}.

Locked research design:
{lock_yaml}

Protocol type: {protocol_type}

Source data schemas:
{source_schemas}

AVAILABLE PYTHON ENVIRONMENT (your script can import these without
adding to requirements):
- Standard library: csv, json, re, math, statistics, datetime, pathlib,
  collections, itertools, functools (everything in Python 3.11+ stdlib)
- Data-science stack: numpy (as np), pandas (as pd), scipy (scipy.stats
  for tests, scipy.optimize for fitting)
- HTTP / data fetching: httpx (use httpx.Client, not requests)
- Parsing: pyyaml (for YAML), json (for JSON)

DO NOT import:
- requests (use httpx instead)
- matplotlib, seaborn, plotly (no figure generation in this stage —
  describe figures as dicts in result_manifest, the Drafter renders
  LaTeX-native tables)
- scikit-learn, tensorflow, pytorch, transformers (out of scope for
  this stage; if you need ML, fall back to scipy.stats / numpy)
- nltk (use re + manual text processing for token-level work)
- Any package not listed above (the subprocess will fail with
  ModuleNotFoundError — production paper apep_1b62de0c hit exactly
  this with `import krippendorff`)

If you genuinely need a statistic that isn't in numpy/scipy.stats,
implement it from primitives — Krippendorff's alpha is ~30 lines of
numpy. Don't fabricate library calls.

Write a complete, executable Python script that:
1. Loads the source data from CSV files
2. Cleans and prepares variables according to the locked design
3. Implements the specified method/identification strategy
4. Runs the main analysis
5. Performs at least two robustness checks
6. Generates result objects (tables as dicts/lists)
7. Saves a result_manifest.json with all outputs
8. Uses numpy random seed 42 for reproducibility

Also provide a requirements.txt with pinned package versions (use
ONLY the packages listed in AVAILABLE PYTHON ENVIRONMENT above).

Return JSON:
{{
  "code": "<the full Python script>",
  "requirements": "<the requirements.txt content>",
  "expected_outputs": [
    {{"name": "string", "type": "table|figure|statistic", "description": "string"}}
  ]
}}

No markdown, no commentary outside the JSON."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_analysis_code(
    paper_id: str,
    provider: LLMProvider | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Generate analysis code based on locked design and source data.

    Internally manages DB sessions in three phases (read → LLM → write)
    so we never hold a connection across the long LLM call. Without
    this split, asyncpg drops the connection mid-call and the final
    commit fails (production run #25135681422 hit this at ~11 min).

    The ``session`` parameter is kept for back-compat but ignored —
    every DB phase opens its own short-lived ``async_session()``.

    1. Read lock artifact + source schemas (short session)
    2. Generate Python analysis script via LLM (no session held)
    3. Persist funnel_stage update (short session)
    4. Return code content, requirements, and expected outputs
    """
    del session  # explicitly ignored; see docstring

    # ── Phase 1: reads (short-lived session) ─────────────────────────
    async with async_session() as s:
        paper = await _load_paper(s, paper_id)
        lock = await _load_active_lock(s, paper_id)
        if lock is None:
            raise ValueError(
                f"No active lock artifact for paper '{paper_id}'. "
                "Design must be locked before generating analysis code."
            )
        source_schemas = await _build_source_schemas(s, paper_id)
        # Copy values OUT of the session so we can use them after closing.
        lock_yaml = lock.lock_yaml
        protocol_type = lock.lock_protocol_type
        del paper  # don't reuse a session-bound instance after close

    # ── Phase 2: LLM call (no session held) ──────────────────────────
    if provider is None:
        provider, model = await get_generation_provider()
    else:
        from app.config import settings

        model = settings.claude_opus_model

    prompt = ANALYSIS_USER_PROMPT.format(
        paper_id=paper_id,
        lock_yaml=lock_yaml,
        protocol_type=protocol_type,
        source_schemas=source_schemas if source_schemas else "(no snapshots available)",
    )

    response = await provider.complete(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        temperature=0.3,
        # Hold at 16K to fit inside Render's ~15-min HTTP request
        # limit. PR #32 bumped this to 32K to recover from a one-off
        # truncation, but the bigger budget pushed total pipeline
        # runtime past the wall (run #25145786347 streamed for 14m47s
        # then was killed mid-stage). The salvage path added in PR #32
        # still handles any truncation that does occur, so we don't
        # actually lose work — partial code is recovered. Once we
        # migrate to fire-and-poll (no held HTTP connection) this can
        # be re-bumped.
        max_tokens=16384,
    )

    parsed = _parse_json_object(response)
    code_content = parsed.get("code", "")

    if not code_content:
        # Surface the actual LLM response (truncated) so the cron
        # payload tells us why parsing failed. Without this, the
        # operator sees only "No analysis code generated" and has
        # no way to distinguish JSON-truncation, prose-only response,
        # or model refusal.
        head = response[:300] if response else "(empty response)"
        tail = response[-300:] if len(response) > 600 else ""
        raise RuntimeError(
            f"Analyst LLM returned no parseable code. "
            f"Response length: {len(response)}. "
            f"Head: {head!r}. Tail: {tail!r}"
        )

    requirements = parsed.get(
        "requirements",
        "numpy>=1.24.0\npandas>=2.0.0\nstatsmodels>=0.14.0\nscipy>=1.11.0\n",
    )
    expected_outputs = parsed.get("expected_outputs", [])
    code_hash = hash_content(code_content.encode("utf-8"))

    # ── Phase 3: write (short-lived session, fresh connection) ───────
    async with async_session() as s:
        paper = await _load_paper(s, paper_id)
        paper.funnel_stage = "analyzing"
        s.add(paper)
        await s.commit()

    logger.info(
        "Analyst generated code for paper %s (hash=%s, %d expected outputs)",
        paper_id,
        code_hash[:16],
        len(expected_outputs),
    )

    return {
        "code": code_content,
        "requirements": requirements,
        "expected_outputs": expected_outputs,
        "code_hash": code_hash,
    }


async def execute_analysis(
    paper_id: str,
    code_content: str,
    use_container: bool = False,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute analysis code and extract result objects.

    For dev: uses subprocess with resource limits.
    For prod: would use Docker container (when available).

    Internally manages DB sessions so we never hold a connection
    across the subprocess call (which can take minutes).

    The ``session`` parameter is kept for back-compat but ignored.

    Returns result_manifest with:
    - tables: list of generated table descriptions
    - figures: list of generated figure descriptions
    - result_objects: dict of named results for claim-linking
    - execution_log: stdout/stderr
    - code_hash, output_hash
    """
    del session  # explicitly ignored

    code_hash = hash_content(code_content.encode("utf-8"))

    # ── Subprocess (no session held) ─────────────────────────────────
    if use_container:
        result = await _execute_in_container(code_content)
    else:
        result = await _execute_in_subprocess(code_content)

    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    exit_code = result.get("exit_code", -1)

    # Parse result_manifest.json if the script produced one
    result_manifest = _parse_result_manifest(stdout)

    # Compute output hash from the combined results
    output_data = json.dumps(result_manifest, sort_keys=True).encode("utf-8")
    output_hash = hash_content(output_data)

    # ── Persist funnel stage if execution succeeded (fresh session) ──
    if exit_code == 0:
        async with async_session() as s:
            paper = await _load_paper(s, paper_id)
            paper.funnel_stage = "analyzing"
            s.add(paper)
            await s.commit()

    execution_result = {
        "tables": result_manifest.get("tables", []),
        "figures": result_manifest.get("figures", []),
        "result_objects": result_manifest.get("result_objects", {}),
        "execution_log": {
            "stdout": stdout[-5000:],  # Last 5000 chars
            "stderr": stderr[-2000:],  # Last 2000 chars
            "exit_code": exit_code,
        },
        "code_hash": code_hash,
        "output_hash": output_hash,
        "success": exit_code == 0,
    }

    logger.info(
        "Analyst executed code for paper %s (exit=%d, code_hash=%s, output_hash=%s)",
        paper_id,
        exit_code,
        code_hash[:16],
        output_hash[:16],
    )
    return execution_result


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


async def _build_source_schemas(session: AsyncSession, paper_id: str) -> str:
    """Build a text summary of available source data schemas for the LLM."""
    # Get recent snapshots (across all sources) for context
    stmt = select(SourceSnapshot).order_by(SourceSnapshot.fetched_at.desc()).limit(20)
    result = await session.execute(stmt)
    snapshots = result.scalars().all()

    if not snapshots:
        return ""

    lines: list[str] = []
    for snap in snapshots:
        params = snap.fetch_parameters or "{}"
        lines.append(
            f"- Source: {snap.source_card_id} | "
            f"Records: {snap.record_count or 'N/A'} | "
            f"Size: {snap.file_size_bytes or 'N/A'} bytes | "
            f"Params: {params}"
        )
    return "\n".join(lines)


def _parse_json_object(response: str) -> dict:
    """Parse a JSON object from an LLM response.

    Tolerant to:
      - markdown code fences (```json ... ```)
      - leading/trailing whitespace and prose
      - truncated responses (extracts the ``code`` field via regex
        even when the closing brace is missing)

    Logs the response head/tail on parse failure so the operator
    can see what the LLM actually returned (production run
    #25138860483 hit "No analysis code generated" with no diagnostic).
    """
    if not response:
        logger.warning(
            "Empty LLM response — cannot parse analysis JSON. Returning fallback."
        )
        return {"code": "", "requirements": "", "expected_outputs": []}

    # Try the full-JSON-extract path first.
    try:
        start = response.index("{")
        end = response.rindex("}") + 1
        return json.loads(response[start:end])
    except (ValueError, json.JSONDecodeError) as exc:
        # Log enough of the response to diagnose without dumping
        # 16K of tokens. Head + tail covers truncation, fence
        # wrapping, and "I cannot do that" prose-only responses.
        head = response[:500]
        tail = response[-500:] if len(response) > 1000 else ""
        logger.warning(
            "Failed to parse analysis JSON (%s: %s).\n"
            "Response length: %d chars.\n"
            "First 500 chars: %r\n"
            "Last 500 chars: %r",
            type(exc).__name__,
            exc,
            len(response),
            head,
            tail,
        )

    # Truncation salvage: try to extract the ``code`` field via regex
    # in case Claude was cut off mid-response.
    import re

    # First try the well-terminated case (response has a closing quote).
    code_match = re.search(r'"code"\s*:\s*"((?:[^"\\]|\\.)*)"', response, re.DOTALL)
    if code_match:
        logger.warning(
            "Salvaged ``code`` field from JSON with closing quote (%d chars).",
            len(code_match.group(1)),
        )
        try:
            code = json.loads(f'"{code_match.group(1)}"')
        except json.JSONDecodeError:
            code = code_match.group(1).encode().decode("unicode_escape")
        return {
            "code": code,
            "requirements": "numpy>=1.24.0\npandas>=2.0.0\nstatsmodels>=0.14.0\nscipy>=1.11.0\n",
            "expected_outputs": [],
        }

    # Truncated mid-string case: response stops before the closing
    # quote. Find the start of the ``code`` value and take everything
    # to the end of the response (production run #25144668610 hit
    # this — 56K chars, ended mid-function).
    open_match = re.search(r'"code"\s*:\s*"', response)
    if open_match:
        raw = response[open_match.end() :]
        # Trim a trailing markdown fence if present
        raw = re.sub(r"\n?```\s*$", "", raw)
        try:
            code = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            try:
                code = raw.encode().decode("unicode_escape")
            except UnicodeDecodeError:
                code = raw
        if code:
            logger.warning(
                "Salvaged ``code`` field from truncated JSON (%d chars).",
                len(code),
            )
            return {
                "code": code,
                "requirements": "numpy>=1.24.0\npandas>=2.0.0\nstatsmodels>=0.14.0\nscipy>=1.11.0\n",
                "expected_outputs": [],
            }

    return {"code": "", "requirements": "", "expected_outputs": []}


async def _execute_in_subprocess(code_content: str) -> dict[str, Any]:
    """Execute Python code in a sandboxed subprocess with resource limits.

    Security measures:
    - Runs in an isolated temp directory
    - 120-second wall-clock timeout
    - 512 MB virtual memory limit (ulimit)
    - 60-second CPU time limit (ulimit)
    - Network imports are not blocked but analysis code runs unprivileged
    """
    with tempfile.TemporaryDirectory(prefix="ape_analysis_") as tmpdir:
        script_path = os.path.join(tmpdir, "analysis.py")
        with open(script_path, "w") as f:
            f.write(code_content)

        # Write a runner script that sets resource limits and executes
        runner = f"""\
import resource
import sys
import os

# Resource limits: 512 MB virtual memory, 60s CPU time
try:
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
except (ValueError, resource.error):
    pass  # May not be supported on all platforms

sys.path.insert(0, '{tmpdir}')
os.chdir('{tmpdir}')

try:
    exec(open('{script_path}').read())
except MemoryError:
    print("ANALYSIS_ERROR: Memory limit exceeded (512 MB)", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ANALYSIS_ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
        runner_path = os.path.join(tmpdir, "runner.py")
        with open(runner_path, "w") as f:
            f.write(runner)

        try:
            # Use ``sys.executable`` (the venv's Python) instead of bare
            # ``python3`` so the subprocess inherits the same packages
            # the backend has — numpy / pandas / scipy from PR #63.
            # Bare ``python3`` resolves via PATH to the system Python on
            # Render, which has only stdlib. Production paper
            # apep_1b62de0c hit "ANALYSIS_ERROR: No module named 'numpy'"
            # for exactly this reason.
            import sys

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                runner_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
            return {
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode or 0,
            }
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            return {
                "stdout": "",
                "stderr": "Execution timed out after 120 seconds",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution failed: {e}",
                "exit_code": -1,
            }


async def _execute_in_container(code_content: str) -> dict[str, Any]:
    """Execute Python code in an isolated Docker container.

    Uses a minimal Python image with:
    - No network access (--network none)
    - 512 MB memory limit
    - Read-only root filesystem (tmpdir mounted as /work)
    - 120-second timeout

    Falls back to subprocess if Docker is unavailable.
    """
    import shutil

    if not shutil.which("docker"):
        logger.warning("Docker not available; falling back to sandboxed subprocess")
        return await _execute_in_subprocess(code_content)

    with tempfile.TemporaryDirectory(prefix="ape_analysis_") as tmpdir:
        script_path = os.path.join(tmpdir, "analysis.py")
        with open(script_path, "w") as f:
            f.write(code_content)

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--read-only",
                "--tmpfs",
                "/tmp:size=64m",
                "-v",
                f"{tmpdir}:/work:rw",
                "-w",
                "/work",
                "python:3.11-slim",
                "python3",
                "/work/analysis.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )
            return {
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode or 0,
            }
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
            # Force-remove the container if stuck
            await asyncio.create_subprocess_exec("docker", "kill", "--signal", "KILL")
            return {
                "stdout": "",
                "stderr": "Container execution timed out after 120 seconds",
                "exit_code": -1,
            }
        except Exception as e:
            logger.warning(
                "Docker execution failed: %s — falling back to subprocess", e
            )
            return await _execute_in_subprocess(code_content)


def _parse_result_manifest(stdout: str) -> dict[str, Any]:
    """Parse a result_manifest from script stdout.

    The analysis script is expected to print a JSON object as its last
    meaningful output, or produce a result_manifest.json file.
    """
    # Try to find a JSON object in stdout
    try:
        # Look for the last JSON object in stdout
        last_brace = stdout.rindex("}")
        # Walk backwards to find matching opening brace
        depth = 0
        start = last_brace
        for i in range(last_brace, -1, -1):
            if stdout[i] == "}":
                depth += 1
            elif stdout[i] == "{":
                depth -= 1
                if depth == 0:
                    start = i
                    break
        candidate = stdout[start : last_brace + 1]
        return json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        pass

    # Return a minimal manifest if nothing was parsed
    return {
        "tables": [],
        "figures": [],
        "result_objects": {},
    }
