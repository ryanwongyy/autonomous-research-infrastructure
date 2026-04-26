import logging
import re

logger = logging.getLogger(__name__)

SUSPICIOUS_PATTERNS = [
    (r"set\.seed\(\d+\)", "Fixed random seed may indicate fabricated data"),
    (r"rnorm\(|runif\(|rbinom\(", "Random number generation suggests simulated data"),
    (r"np\.random\.", "NumPy random functions suggest simulated data"),
    (r"sample\(.*replace\s*=\s*TRUE", "Sampling with replacement in suspicious context"),
    (r"#.*TODO|#.*FIXME|#.*HACK", "Incomplete code markers found"),
    (r"hardcoded|hard.coded", "Reference to hardcoded values"),
    (r"fake|dummy|mock|placeholder", "Reference to fake/dummy data"),
    (r"result\s*=\s*[\d.]+", "Hardcoded result assignment"),
]


def scan_code(code: str) -> list[dict]:
    """Scan analysis code for suspicious patterns.

    Returns a list of issues found, each with pattern, description, and line number.
    """
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        for pattern, description in SUSPICIOUS_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                issues.append({
                    "line": i,
                    "pattern": pattern,
                    "description": description,
                    "content": line.strip()[:100],
                })

    return issues


def compute_virtual_losses(issues: list[dict]) -> int:
    """Compute virtual losses (rating penalty) based on severity of issues.

    Returns number of virtual losses to apply.
    """
    critical_keywords = {"fabricated", "simulated", "hardcoded", "fake"}
    virtual_losses = 0

    for issue in issues:
        desc_lower = issue["description"].lower()
        if any(kw in desc_lower for kw in critical_keywords):
            virtual_losses += 2
        else:
            virtual_losses += 1

    return min(virtual_losses, 5)  # Cap at 5
