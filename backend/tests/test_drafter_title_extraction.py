"""Regression test: Drafter must populate paper.title from the manuscript.

Background: production paper apep_faf874ae was successfully generated
end-to-end (8 stages completed, 26 sourced claims, real data) but its
``papers.title`` row still showed the placeholder ``"Generating..."``
because the Drafter never lifted the title out of the LaTeX it produced.
"""

from __future__ import annotations

from app.services.paper_generation.roles.drafter import _extract_latex_title


def test_extracts_simple_title():
    src = (
        r"\documentclass{article}\title{Algorithmic Accountability in EU AI Regulation}\author{...}"
    )
    assert _extract_latex_title(src) == "Algorithmic Accountability in EU AI Regulation"


def test_extracts_multiline_title():
    src = "\\title{\n  A long\n  multi-line title\n}\n\\author{}"
    assert _extract_latex_title(src) == "A long\n  multi-line title"


def test_strips_simple_latex_commands():
    src = r"\title{Foo: \emph{Bar} and \textbf{Baz}}"
    assert _extract_latex_title(src) == "Foo: Bar and Baz"


def test_returns_none_when_no_title():
    assert _extract_latex_title(r"\documentclass{article}\author{X}\maketitle") is None


def test_returns_none_for_empty_input():
    assert _extract_latex_title("") is None
    assert _extract_latex_title(None) is None


def test_caps_at_512_chars():
    long_title = "A" * 1000
    src = f"\\title{{{long_title}}}"
    result = _extract_latex_title(src)
    assert result is not None
    assert len(result) == 512
