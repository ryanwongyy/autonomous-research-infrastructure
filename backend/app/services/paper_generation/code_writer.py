import logging
import os
from dataclasses import dataclass

from app.services.llm.router import get_generation_provider
from app.services.paper_generation.data_fetcher import DataResult
from app.services.paper_generation.idea_generator import ResearchIdea

logger = logging.getLogger(__name__)


@dataclass
class CodeResult:
    success: bool
    scripts: list[str]
    analysis_tool: str
    error: str | None = None


CODE_PROMPT = """You are writing analysis code for a research paper.

Research question: {research_question}
Method: {method}
Identification strategy: {identification_strategy}
Data files: {data_files}
Columns: {columns}
Analysis tool: {analysis_tool}

Write a complete, executable {analysis_tool} script that:
1. Loads the data
2. Cleans and prepares variables
3. Runs the main analysis ({method})
4. Performs robustness checks
5. Generates tables and figures
6. Saves all outputs

Write ONLY the code, no explanations. Use real statistical packages."""


async def write_analysis_code(
    idea: ResearchIdea,
    data_result: DataResult,
    paper_dir: str,
    domain_config_id: str,
) -> CodeResult:
    """Generate analysis code using LLM."""
    code_dir = os.path.join(paper_dir, "code")
    os.makedirs(code_dir, exist_ok=True)

    # Determine analysis tool from domain config
    analysis_tool = "python"  # Default; would read from domain config

    provider, model = await get_generation_provider()

    prompt = CODE_PROMPT.format(
        research_question=idea.research_question,
        method=idea.method,
        identification_strategy=idea.identification_strategy,
        data_files=", ".join(data_result.files),
        columns=", ".join(data_result.columns),
        analysis_tool=analysis_tool,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.3,
        max_tokens=8192,
    )

    # Extract code from response
    code = _extract_code(response, analysis_tool)

    ext = ".py" if analysis_tool == "python" else ".R"
    script_path = os.path.join(code_dir, f"analysis{ext}")
    with open(script_path, "w") as f:
        f.write(code)

    return CodeResult(
        success=True,
        scripts=[script_path],
        analysis_tool=analysis_tool,
    )


def _extract_code(response: str, language: str) -> str:
    """Extract code block from LLM response."""
    # Try to find code between triple backticks
    markers = [f"```{language}", "```python", "```r", "```R", "```"]
    for marker in markers:
        if marker in response:
            start = response.index(marker) + len(marker)
            end = response.index("```", start) if "```" in response[start:] else len(response)
            return response[start:end].strip()

    # If no code block, return the whole response (assume it's all code)
    return response.strip()
