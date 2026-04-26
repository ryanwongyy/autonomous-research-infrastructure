import logging
import os
import subprocess
from dataclasses import dataclass

from app.services.llm.router import get_generation_provider
from app.services.paper_generation.code_writer import CodeResult
from app.services.paper_generation.data_fetcher import DataResult
from app.services.paper_generation.idea_generator import ResearchIdea

logger = logging.getLogger(__name__)


@dataclass
class PaperResult:
    success: bool
    tex_path: str | None = None
    pdf_path: str | None = None
    error: str | None = None
    compilation_error: str | None = None


COMPOSE_PROMPT = """Write a complete LaTeX research paper.

Title: {title}
Abstract: {abstract}
Research Question: {research_question}
Method: {method}
Identification Strategy: {identification_strategy}
Data Description: {data_description}

The paper should follow standard economics paper structure:
1. Introduction (with research question and contribution)
2. Institutional Background / Literature Review
3. Data (describe sources and summary statistics)
4. Empirical Strategy (identification and estimation)
5. Results (main findings with tables reference)
6. Robustness Checks
7. Conclusion (policy implications)

Use \\documentclass{{article}} with standard packages.
Include placeholder \\input{{}} commands for tables and figures.
Write ONLY valid LaTeX code."""


async def compose_paper(
    idea: ResearchIdea,
    data_result: DataResult,
    code_result: CodeResult,
    paper_dir: str,
) -> PaperResult:
    """Compose a complete LaTeX research paper."""
    provider, model = await get_generation_provider()

    prompt = COMPOSE_PROMPT.format(
        title=idea.title,
        abstract=idea.abstract,
        research_question=idea.research_question,
        method=idea.method,
        identification_strategy=idea.identification_strategy,
        data_description=data_result.description,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.5,
        max_tokens=16384,
    )

    # Extract LaTeX
    tex_content = _extract_latex(response)

    tex_path = os.path.join(paper_dir, "paper.tex")
    with open(tex_path, "w") as f:
        f.write(tex_content)

    # Compile LaTeX to PDF (requires texlive)
    pdf_path = None
    compilation_error = None
    try:
        # Run pdflatex twice for cross-references
        for pass_num in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", paper_dir, tex_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0 and pass_num == 1:
                compilation_error = result.stderr[:500] if result.stderr else "pdflatex returned non-zero"
                logger.warning("pdflatex failed (pass %d): %s", pass_num + 1, compilation_error)

        candidate = os.path.join(paper_dir, "paper.pdf")
        if os.path.exists(candidate):
            size = os.path.getsize(candidate)
            if size > 1024:  # Valid PDFs are >1KB
                pdf_path = candidate
                logger.info("PDF compiled successfully (%d bytes)", size)
            else:
                logger.warning("PDF file too small (%d bytes) — likely corrupt", size)
        else:
            logger.warning("pdflatex ran but no PDF produced")

    except FileNotFoundError:
        logger.info("pdflatex not installed — skipping PDF compilation")
    except subprocess.TimeoutExpired:
        logger.warning("pdflatex timed out after 60 seconds")

    return PaperResult(
        success=True,
        tex_path=tex_path,
        pdf_path=pdf_path,
        compilation_error=compilation_error,
    )


def _extract_latex(response: str) -> str:
    """Extract LaTeX from LLM response."""
    if "```latex" in response:
        start = response.index("```latex") + 8
        end = response.index("```", start) if "```" in response[start:] else len(response)
        return response[start:end].strip()
    elif "```tex" in response:
        start = response.index("```tex") + 6
        end = response.index("```", start) if "```" in response[start:] else len(response)
        return response[start:end].strip()
    elif "\\documentclass" in response:
        start = response.index("\\documentclass")
        return response[start:].strip()
    return response.strip()
