"""CSL-JSON citation management with provenance metadata."""

from __future__ import annotations

import json
import re
from typing import Any

from app.models.source_card import SourceCard


def create_csl_entry(
    source_card: SourceCard,
    title: str,
    access_date: str,
    source_hash: str,
    url: str | None = None,
    authors: list[dict] | None = None,
    date_issued: str | None = None,
    **extra_fields: Any,
) -> dict:
    """Create a CSL-JSON citation object with provenance metadata.

    Returns a dict conforming to CSL-JSON spec with extra fields:
    - x-source-hash: SHA-256 of source content
    - x-source-tier: A/B/C
    - x-claim-permissions: what the source can support
    - x-access-date: when it was accessed
    """
    # Build a stable citation ID from the source card id and hash prefix.
    citation_id = f"{source_card.id}_{source_hash[:12]}"

    entry: dict[str, Any] = {
        "id": citation_id,
        "type": _map_source_type_to_csl(source_card.source_type),
        "title": title,
        "accessed": _parse_date_parts(access_date),
    }

    # Authors
    if authors:
        entry["author"] = authors
    else:
        # Use the source name as an institutional author.
        entry["author"] = [{"literal": source_card.name}]

    # URL
    effective_url = url or source_card.url
    if effective_url:
        entry["URL"] = effective_url

    # Issued date
    if date_issued:
        entry["issued"] = _parse_date_parts(date_issued)

    # Provenance extension fields (prefixed with x- per CSL convention).
    entry["x-source-hash"] = source_hash
    entry["x-source-tier"] = source_card.tier
    entry["x-claim-permissions"] = source_card.claim_permissions
    entry["x-access-date"] = access_date

    # Merge any additional fields.
    for key, value in extra_fields.items():
        entry[key] = value

    return entry


def generate_bibliography(
    citations: list[dict], style: str = "apa"
) -> list[str]:
    """Generate formatted bibliography strings from CSL-JSON entries.

    Basic implementation covering APA and Chicago styles.
    Falls back to a generic format for unknown styles.
    """
    entries: list[str] = []

    for cit in citations:
        if style == "apa":
            entries.append(_format_apa(cit))
        elif style == "chicago":
            entries.append(_format_chicago(cit))
        else:
            entries.append(_format_generic(cit))

    return entries


def export_csl_json(citations: list[dict]) -> str:
    """Export citations as CSL-JSON string."""
    return json.dumps(citations, indent=2, ensure_ascii=False)


def export_bibtex(citations: list[dict]) -> str:
    """Convert CSL-JSON entries to BibTeX format string."""
    bibtex_entries: list[str] = []

    for cit in citations:
        entry_type = _csl_type_to_bibtex(cit.get("type", "article"))
        entry_id = _sanitise_bibtex_key(cit.get("id", "unknown"))
        fields: list[str] = []

        # Title
        if "title" in cit:
            fields.append(f"  title = {{{cit['title']}}}")

        # Author
        if "author" in cit:
            author_str = _format_bibtex_authors(cit["author"])
            fields.append(f"  author = {{{author_str}}}")

        # Year
        year = _extract_year(cit)
        if year:
            fields.append(f"  year = {{{year}}}")

        # URL
        if "URL" in cit:
            fields.append(f"  url = {{{cit['URL']}}}")

        # Note with provenance hash
        if "x-source-hash" in cit:
            fields.append(f"  note = {{SHA-256: {cit['x-source-hash']}}}")

        body = ",\n".join(fields)
        bibtex_entries.append(f"@{entry_type}{{{entry_id},\n{body}\n}}")

    return "\n\n".join(bibtex_entries)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _map_source_type_to_csl(source_type: str) -> str:
    """Map the project's source_type strings to CSL-JSON types."""
    mapping = {
        "government_registry": "legislation",
        "court_database": "legal_case",
        "journal_article": "article-journal",
        "working_paper": "report",
        "dataset": "dataset",
        "news": "article-newspaper",
        "book": "book",
        "webpage": "webpage",
    }
    return mapping.get(source_type, "article")


def _parse_date_parts(date_str: str) -> dict:
    """Parse a date string (YYYY, YYYY-MM, or YYYY-MM-DD) into CSL date-parts."""
    parts = date_str.split("-")
    int_parts = [int(p) for p in parts if p.isdigit()]
    return {"date-parts": [int_parts]} if int_parts else {"raw": date_str}


def _extract_year(cit: dict) -> str | None:
    """Extract a year string from a CSL-JSON entry."""
    issued = cit.get("issued") or cit.get("accessed")
    if not issued:
        return None
    date_parts = issued.get("date-parts")
    if date_parts and date_parts[0]:
        return str(date_parts[0][0])
    raw = issued.get("raw", "")
    match = re.search(r"\d{4}", raw)
    return match.group(0) if match else None


def _format_authors_inline(authors: list[dict]) -> str:
    """Format authors for inline bibliography display."""
    names: list[str] = []
    for a in authors:
        if "literal" in a:
            names.append(a["literal"])
        elif "family" in a:
            given = a.get("given", "")
            names.append(f"{a['family']}, {given[0]}." if given else a["family"])
        else:
            names.append("Unknown")
    if len(names) <= 2:
        return " & ".join(names)
    return f"{names[0]} et al."


def _format_apa(cit: dict) -> str:
    """Format a single citation in APA style."""
    authors = _format_authors_inline(cit.get("author", []))
    year = _extract_year(cit) or "n.d."
    title = cit.get("title", "Untitled")
    url_part = f" Retrieved from {cit['URL']}" if "URL" in cit else ""
    return f"{authors} ({year}). {title}.{url_part}"


def _format_chicago(cit: dict) -> str:
    """Format a single citation in Chicago style."""
    authors = _format_authors_inline(cit.get("author", []))
    year = _extract_year(cit) or "n.d."
    title = cit.get("title", "Untitled")
    url_part = f" {cit['URL']}." if "URL" in cit else ""
    return f"{authors}. {year}. \"{title}.\"{url_part}"


def _format_generic(cit: dict) -> str:
    """Fallback format: Author (Year). Title. URL."""
    authors = _format_authors_inline(cit.get("author", []))
    year = _extract_year(cit) or "n.d."
    title = cit.get("title", "Untitled")
    url_part = f" {cit['URL']}" if "URL" in cit else ""
    return f"{authors} ({year}). {title}.{url_part}"


def _csl_type_to_bibtex(csl_type: str) -> str:
    """Map CSL-JSON type to BibTeX entry type."""
    mapping = {
        "article-journal": "article",
        "report": "techreport",
        "book": "book",
        "chapter": "inbook",
        "legislation": "misc",
        "legal_case": "misc",
        "dataset": "misc",
        "article-newspaper": "misc",
        "webpage": "misc",
    }
    return mapping.get(csl_type, "misc")


def _sanitise_bibtex_key(key: str) -> str:
    """Sanitise a string for use as a BibTeX citation key."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", key)


def _format_bibtex_authors(authors: list[dict]) -> str:
    """Format author list for BibTeX (Last, First and ...)."""
    parts: list[str] = []
    for a in authors:
        if "literal" in a:
            parts.append(a["literal"])
        elif "family" in a:
            given = a.get("given", "")
            parts.append(f"{a['family']}, {given}" if given else a["family"])
        else:
            parts.append("Unknown")
    return " and ".join(parts)
