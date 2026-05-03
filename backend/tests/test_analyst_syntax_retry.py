"""Tests that the Analyst validates Python syntax and retries the
LLM with error context when the generated code won't compile.

Production paper apep_9afaf116 (autonomous-loop run 25217093244) had
its Analyst stage fail with:
  ANALYSIS_ERROR: SyntaxError: unterminated string literal
    (detected at line N)

The LLM produced 16K characters of valid-looking Python with one
missing closing quote. The pipeline noticed this only AFTER spawning
the subprocess (~30s wasted), and the failure produced no result
objects so the Drafter framing path (PR #67) had to reframe the
paper as research-design.

This PR adds:
  * ``_validate_python_syntax`` — a compile()-based check that runs
    in microseconds before the subprocess.
  * A retry prompt (``SYNTAX_RETRY_PROMPT``) that sends the broken
    code + error message back to the LLM for correction.
  * One retry only — if the retry also fails, the broken code falls
    through to the existing ANALYSIS_ERROR path so PR #67 can still
    reframe the paper.

This file locks in:
  * The validator catches the actual production failure pattern.
  * The validator handles edge cases (empty, valid, multi-line errors).
  * The retry path is wired into ``generate_analysis_code`` (source
    inspection — exercising it end-to-end requires mocking the LLM).
  * The retry prompt structure is correct.
"""

from __future__ import annotations

import inspect

from app.services.paper_generation.roles import analyst as analyst_mod
from app.services.paper_generation.roles.analyst import (
    SYNTAX_RETRY_PROMPT,
    _validate_python_syntax,
    generate_analysis_code,
)

# ── _validate_python_syntax ────────────────────────────────────────────────


def test_validator_returns_none_on_valid_code():
    """The simple positive case — a one-liner."""
    assert _validate_python_syntax("x = 1") is None


def test_validator_returns_none_on_realistic_analysis_code():
    """Multi-line Python with imports, fn defs, control flow."""
    code = (
        "import numpy as np\n"
        "import pandas as pd\n"
        "\n"
        "def main():\n"
        "    df = pd.read_csv('data.csv')\n"
        "    arr = df['x'].to_numpy()\n"
        "    return arr.mean()\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print(main())\n"
    )
    assert _validate_python_syntax(code) is None


def test_validator_catches_unterminated_string_literal():
    """The exact pattern that killed production paper apep_9afaf116."""
    code = 'x = "this string never closes\nprint(x)\n'
    err = _validate_python_syntax(code)
    assert err is not None
    assert "SyntaxError" in err
    # The error must mention the offending line so the LLM has a
    # chance of fixing it.
    assert "line 1" in err or "line 2" in err


def test_validator_catches_unmatched_paren():
    code = "result = func(a, b, c\nprint(result)\n"
    err = _validate_python_syntax(code)
    assert err is not None
    assert "SyntaxError" in err


def test_validator_catches_invalid_indentation():
    code = "def foo():\n    x = 1\n  y = 2\n"  # y indent inconsistent
    err = _validate_python_syntax(code)
    assert err is not None


def test_validator_handles_empty_string():
    """Empty input must return a sentinel error, not raise — the
    caller treats it as a 'retry needed' signal."""
    err = _validate_python_syntax("")
    assert err is not None
    assert "no code" in err.lower() or "empty" in err.lower()


def test_validator_handles_whitespace_only():
    """A few spaces / newlines is effectively empty."""
    err = _validate_python_syntax("   \n\n  ")
    assert err is not None


def test_validator_error_string_is_short():
    """The error goes back to the LLM in the retry prompt; verbose
    tracebacks would consume the response budget."""
    err = _validate_python_syntax('x = "unterminated\n')
    assert err is not None
    # Sanity bound — ~200 chars max. If we ever wire in a full
    # traceback this test catches it.
    assert len(err) < 500


# ── SYNTAX_RETRY_PROMPT structure ──────────────────────────────────────────


def test_retry_prompt_has_required_placeholders():
    """The prompt format() will KeyError without these placeholders."""
    assert "{syntax_error}" in SYNTAX_RETRY_PROMPT
    assert "{prior_code}" in SYNTAX_RETRY_PROMPT


def test_retry_prompt_constrains_scope_to_syntax():
    """We do NOT want the LLM to redesign the analysis on retry —
    just fix the syntax. The prompt must say so."""
    flat = " ".join(SYNTAX_RETRY_PROMPT.split())
    # Some phrasing of "only fix syntax" must be present.
    assert "ONLY" in SYNTAX_RETRY_PROMPT or "only" in flat
    assert "syntax" in flat.lower()
    # And explicitly preserve the analysis logic.
    assert "do not redesign" in flat.lower() or "same analysis" in flat.lower()


def test_retry_prompt_lists_common_causes():
    """The LLM does better when given a hint about what to look for —
    list the syntax errors most likely from a 16K-token code-gen
    response."""
    assert "unterminated string" in SYNTAX_RETRY_PROMPT
    assert "unmatched" in SYNTAX_RETRY_PROMPT or "parenthesis" in SYNTAX_RETRY_PROMPT


def test_retry_prompt_specifies_json_response_shape():
    """The retry must echo back the same JSON shape — otherwise
    _parse_json_object on the retry response would extract nothing."""
    assert '"code"' in SYNTAX_RETRY_PROMPT
    assert '"requirements"' in SYNTAX_RETRY_PROMPT
    assert '"expected_outputs"' in SYNTAX_RETRY_PROMPT


# ── generate_analysis_code wires retry in ──────────────────────────────────


def test_generate_calls_validator_after_parse():
    """Source check: validation runs after the JSON parse and
    before the function returns. Without this, broken code reaches
    the subprocess unchanged."""
    src = inspect.getsource(generate_analysis_code)
    assert "_validate_python_syntax" in src
    # The validator's result gates a retry branch.
    assert "syntax_error is not None" in src or "syntax_error:" in src


def test_generate_uses_retry_prompt_when_invalid():
    """Source check: SYNTAX_RETRY_PROMPT is referenced in the retry
    branch so the prompt actually reaches the LLM."""
    src = inspect.getsource(generate_analysis_code)
    assert "SYNTAX_RETRY_PROMPT" in src
    # The retry calls provider.complete() a second time.
    assert "retry_response" in src or "provider.complete" in src


def test_generate_uses_retry_code_when_retry_succeeds():
    """Source check: when the retry produces valid code, it replaces
    code_content. Without this assignment, the original broken code
    would still go to the subprocess."""
    src = inspect.getsource(generate_analysis_code)
    assert "code_content = retry_code" in src


def test_generate_falls_through_when_retry_also_broken():
    """Source check: a failing retry must not raise. The existing
    ANALYSIS_ERROR path handles the broken code, and PR #67 reframes
    the paper. Adding a raise here would regress the failure mode
    from soft (research-design paper) to hard (stage failure)."""
    src = inspect.getsource(generate_analysis_code)
    # Find the retry block and check no `raise` lurks in it.
    retry_pos = src.find("SYNTAX_RETRY_PROMPT")
    assert retry_pos > 0
    # Window of ~2KB after the retry prompt reference covers the
    # whole retry branch.
    window = src[retry_pos : retry_pos + 2000]
    # 'raise' may appear inside string literals (e.g. as part of an
    # error message). It must NOT appear as a bare statement.
    for line in window.splitlines():
        stripped = line.strip()
        # Comments and string-literal lines are fine.
        if (
            stripped.startswith("#")
            or stripped.startswith('"')
            or stripped.startswith("'")
        ):
            continue
        assert not stripped.startswith("raise "), (
            f"Retry branch must not raise — found: {line!r}"
        )


def test_generate_handles_retry_exceptions_gracefully():
    """Source check: the retry call is wrapped in try/except so a
    transient HTTP error during the retry doesn't blow up the stage."""
    src = inspect.getsource(generate_analysis_code)
    # The retry block must contain a try/except.
    retry_pos = src.find("SYNTAX_RETRY_PROMPT")
    assert retry_pos > 0
    window = src[retry_pos : retry_pos + 2500]
    assert "try:" in window
    assert "except" in window


# ── Module imports clean ───────────────────────────────────────────────────


def test_module_exposes_validator_and_prompt():
    """Both pieces must be importable from the module."""
    assert analyst_mod._validate_python_syntax is not None
    assert analyst_mod.SYNTAX_RETRY_PROMPT
    assert analyst_mod.generate_analysis_code is not None
