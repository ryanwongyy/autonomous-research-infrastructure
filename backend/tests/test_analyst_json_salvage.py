"""Regression tests for the Analyst's JSON-parse salvage path.

Background: production run #25144668610 had Analyst's LLM produce
56,592 chars of valid-looking JSON wrapped in markdown fences, but
truncated mid-string before the closing quote. The original salvage
regex only matched well-terminated strings — it didn't fire, the
stage failed.

These tests lock in the truncation-tolerant salvage path.
"""

from __future__ import annotations

from app.services.paper_generation.roles.analyst import _parse_json_object


def test_full_json_is_parsed_normally():
    response = '{"code": "import pandas as pd\\nprint(\'hi\')", "requirements": "pandas", "expected_outputs": []}'
    parsed = _parse_json_object(response)
    assert parsed["code"] == "import pandas as pd\nprint('hi')"


def test_markdown_fenced_json_is_parsed():
    response = '```json\n{"code": "x = 1", "requirements": "", "expected_outputs": []}\n```'
    parsed = _parse_json_object(response)
    assert parsed["code"] == "x = 1"


def test_truncated_mid_string_salvages_partial_code():
    """The exact pattern that killed run #25144668610: response stops
    mid-string with no closing quote.
    """
    response = (
        '```json\n{\n  "code": "#!/usr/bin/env python3\\n'
        "import pandas as pd\\nimport numpy as np\\n"
        "def main():\\n    df = pd.read_csv('data.csv')\\n"
        "    results = analyze(df)\\n    # incomplete..."
    )
    parsed = _parse_json_object(response)
    assert parsed["code"], "salvage path should return non-empty code"
    assert "#!/usr/bin/env python3" in parsed["code"]
    assert "pandas" in parsed["code"]


def test_truncated_with_trailing_fence_is_stripped():
    response = '{"code": "import sys\\nprint(\\"hello\\")\\n# more code...\n```'
    parsed = _parse_json_object(response)
    assert parsed["code"]
    # The salvage shouldn't include the markdown fence
    assert "```" not in parsed["code"]


def test_empty_response_returns_empty_code():
    parsed = _parse_json_object("")
    assert parsed["code"] == ""


def test_prose_only_response_returns_empty_code():
    response = "I'm sorry, I cannot generate code for that request."
    parsed = _parse_json_object(response)
    assert parsed["code"] == ""
