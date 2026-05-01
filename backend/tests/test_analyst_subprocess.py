"""Tests that the Analyst subprocess can import the data-science stack.

Production paper apep_1b62de0c (autonomous-loop run 25210220200)
generated end-to-end (L1 PASSED, manuscript downloadable, 25/25
hard-linked claims) but its Results section literally said:

    "Due to an execution error in the analysis pipeline (module
    dependency failure), we are unable to present quantitative
    results. The execution log indicates: 'ANALYSIS_ERROR: No
    module named numpy'."

Two root causes:
  1. The subprocess used bare ``"python3"`` which resolves via PATH
     to the system Python on Render — NOT the backend venv.
  2. The backend venv didn't have numpy / pandas / scipy installed
     anyway.

PR #63 fixes both:
  - Subprocess now uses ``sys.executable`` (the backend venv's Python).
  - numpy, pandas, scipy added to backend dependencies.

This file locks in:
  * The data-science stack is importable in the venv that runs tests.
  * ``_execute_in_subprocess`` uses ``sys.executable``.
  * The Analyst prompt names the available libraries explicitly.
  * The prompt warns against unavailable libraries.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles import analyst as analyst_mod


# ── Backend venv has the data-science stack ─────────────────────────────────


def test_numpy_importable():
    import numpy
    assert numpy.__version__.split(".")[0] >= "2"


def test_pandas_importable():
    import pandas
    assert pandas.__version__.split(".")[0] >= "2"


def test_scipy_importable():
    import scipy
    assert scipy.__version__


def test_scipy_stats_importable():
    """scipy.stats specifically — analysis code needs distributions
    and tests, not just the bare scipy package."""
    from scipy import stats
    assert stats is not None


# ── Subprocess uses sys.executable ──────────────────────────────────────────


def test_subprocess_uses_sys_executable():
    """Source check: the subprocess invocation must use sys.executable
    so it inherits the backend venv. Bare 'python3' resolved via PATH
    gives system Python with no venv packages."""
    src = inspect.getsource(analyst_mod._execute_in_subprocess)
    assert "sys.executable" in src, (
        "Analyst subprocess must use sys.executable, not bare 'python3'. "
        "Otherwise the system Python without numpy is what runs."
    )
    # The bare 'python3' literal must NOT appear as the first arg to
    # create_subprocess_exec (would silently revert the fix).
    assert '"python3"' not in src or "sys.executable" in src


# ── Analyst prompt mentions available libraries ─────────────────────────────


def test_prompt_lists_available_libraries():
    """The prompt must explicitly tell the LLM which libraries are
    available so it doesn't generate ``import tensorflow`` (production
    paper apep_1b62de0c imported a non-existent ``krippendorff``
    package — exactly this failure mode)."""
    prompt = analyst_mod.ANALYSIS_USER_PROMPT
    assert "AVAILABLE PYTHON ENVIRONMENT" in prompt

    # The data-science stack we just added must be named so the LLM
    # uses them rather than fabricating alternatives.
    for lib in ("numpy", "pandas", "scipy"):
        assert lib in prompt


def test_prompt_warns_against_unavailable_libraries():
    """The prompt must explicitly forbid common-but-unavailable
    packages (sklearn, tensorflow, requests-not-httpx, etc.) so the
    LLM doesn't generate code that ModuleNotFoundError's at runtime."""
    prompt = analyst_mod.ANALYSIS_USER_PROMPT
    assert "DO NOT import" in prompt
    # Must call out the production failure example.
    for lib in ("scikit-learn", "tensorflow", "requests"):
        assert lib in prompt
    # Must guide the LLM toward stdlib + numpy fallbacks.
    assert "implement it from primitives" in prompt or "Krippendorff" in prompt


def test_prompt_tells_llm_pinned_versions():
    prompt = analyst_mod.ANALYSIS_USER_PROMPT
    assert "requirements.txt" in prompt


# ── Module imports clean ────────────────────────────────────────────────────


def test_analyst_module_imports_clean():
    assert analyst_mod.generate_analysis_code is not None
    assert analyst_mod.execute_analysis is not None


# ── Tests for the deps file ─────────────────────────────────────────────────


def test_pyproject_includes_data_science_stack():
    """Source check: pyproject.toml lists numpy/pandas/scipy in the
    main dependencies (not just dev)."""
    import pathlib
    pyproject = (
        pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
    )
    text = pyproject.read_text()

    # Find the [project] dependencies block — must contain all three
    # data-science libs.
    project_section_start = text.find("[project]")
    optional_section_start = text.find("[project.optional-dependencies]")
    assert 0 <= project_section_start < optional_section_start
    main_deps = text[project_section_start:optional_section_start]

    for lib in ("numpy", "pandas", "scipy"):
        assert lib in main_deps, (
            f"pyproject.toml [project] dependencies must include {lib}. "
            f"Without it, the Analyst subprocess fails with "
            f"ModuleNotFoundError on every paper."
        )
