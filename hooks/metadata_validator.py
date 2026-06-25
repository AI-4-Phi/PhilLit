#!/usr/bin/env python3
"""Metadata provenance validator for SubagentStop hook.

Validates that BibTeX bibliographic metadata comes from API output,
not from LLM training data (hallucination).

Validates these fields against JSON API output:
- journal / booktitle
- volume
- number / issue
- pages
- publisher
- year
- doi

Exempt fields (LLM-generated, not validated):
- note
- keywords
- abstract_source
- howpublished

Usage: python metadata_validator.py <bib_file> <json_dir> [--mode=strict|warn]
Output: JSON to stdout
Exit codes: 0 = valid, 1 = validation errors, 2 = file not found/read error
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pybtex.database import parse_file
from pybtex.scanner import PybtexSyntaxError


# Fields that require validation against API output
VALIDATED_FIELDS = {
    'journal', 'booktitle', 'volume', 'number', 'pages', 'publisher', 'year', 'doi'
}

# Fields exempt from validation (LLM-generated content)
EXEMPT_FIELDS = {
    'note', 'keywords', 'abstract_source', 'howpublished', 'url', 'abstract'
}

# Fields that are always required but don't need provenance check
# (title/author are validated by being found in the first place)
IDENTITY_FIELDS = {'author', 'title'}


@dataclass
class SourceMetadata:
    """Metadata extracted from a single API result."""
    doi: Optional[str] = None
    title: str = ""
    container_title: Optional[str] = None  # journal/booktitle
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    source_file: str = ""
    source_api: str = ""  # s2, openalex, crossref, arxiv, philpapers


@dataclass
class MetadataIndex:
    """Index of all metadata values from JSON files."""
    # Maps normalized values to source info
    journals: dict = field(default_factory=dict)  # normalized_name -> [(original, source_file)]
    volumes: dict = field(default_factory=dict)
    issues: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    publishers: dict = field(default_factory=dict)
    years: dict = field(default_factory=dict)  # str(year) -> [source_file]
    dois: dict = field(default_factory=dict)  # normalized_doi -> source_file

    # All extracted metadata objects
    entries: list = field(default_factory=list)


def normalize_pages(pages: str) -> str:
    """Normalize page ranges for comparison.

    Handles variations:
    - "163 - 188" -> "163-188"
    - "163--188" -> "163-188"
    - "163-188" -> "163-188"
    """
    if not pages:
        return ""
    # Remove spaces around dashes
    normalized = re.sub(r'\s*[-–—]+\s*', '-', str(pages))
    return normalized.strip()


def normalize_journal(name: str) -> str:
    """Normalize journal name for comparison.

    - Lowercase
    - Strip "The" prefix
    - Remove extra whitespace
    """
    if not name:
        return ""
    normalized = name.lower().strip()
    # Remove "The" prefix
    if normalized.startswith("the "):
        normalized = normalized[4:]
    # Normalize whitespace
    normalized = " ".join(normalized.split())
    return normalized


def normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    # Remove common prefixes
    prefixes = ["https://doi.org/", "http://doi.org/", "doi:", "doi.org/"]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def parse_s2_result(data: dict, source_file: str) -> list[SourceMetadata]:
    """Parse Semantic Scholar JSON format."""
    results = data.get("results", [])
    entries = []

    for item in results:
        journal_info = item.get("journal") or {}

        entry = SourceMetadata(
            doi=item.get("doi"),
            title=item.get("title", ""),
            container_title=journal_info.get("name") or item.get("venue"),
            volume=str(journal_info.get("volume")) if journal_info.get("volume") else None,
            issue=None,  # S2 doesn't typically provide issue
            pages=journal_info.get("pages"),
            publisher=None,  # S2 doesn't provide publisher
            year=item.get("year"),
            source_file=source_file,
            source_api="s2"
        )
        entries.append(entry)

    return entries


def parse_openalex_result(data: dict, source_file: str) -> list[SourceMetadata]:
    """Parse OpenAlex JSON format."""
    results = data.get("results", [])
    entries = []

    for item in results:
        source = item.get("source") or {}

        entry = SourceMetadata(
            doi=item.get("doi"),
            title=item.get("title", ""),
            container_title=source.get("name"),
            volume=None,  # OpenAlex doesn't typically include volume in our output
            issue=None,
            pages=None,
            publisher=None,
            year=item.get("publication_year"),
            source_file=source_file,
            source_api="openalex"
        )
        entries.append(entry)

    return entries


def parse_crossref_result(data: dict, source_file: str) -> list[SourceMetadata]:
    """Parse CrossRef JSON format (from verify_paper.py output)."""
    results = data.get("results", [])
    entries = []

    for item in results:
        entry = SourceMetadata(
            doi=item.get("doi"),
            title=item.get("title", ""),
            container_title=item.get("container_title"),
            volume=item.get("volume"),
            issue=item.get("issue"),
            pages=item.get("page"),
            publisher=item.get("publisher"),
            year=item.get("year"),
            source_file=source_file,
            source_api="crossref"
        )
        entries.append(entry)

    return entries


def parse_arxiv_result(data: dict, source_file: str) -> list[SourceMetadata]:
    """Parse arXiv JSON format."""
    results = data.get("results", [])
    entries = []

    for item in results:
        # arXiv papers typically don't have traditional journal info
        entry = SourceMetadata(
            doi=item.get("doi"),
            title=item.get("title", ""),
            container_title=item.get("journal_ref"),  # May contain journal if published
            volume=None,
            issue=None,
            pages=None,
            publisher=None,
            year=item.get("published", "")[:4] if item.get("published") else None,
            source_file=source_file,
            source_api="arxiv"
        )
        if entry.year:
            try:
                entry.year = int(entry.year)
            except ValueError:
                entry.year = None
        entries.append(entry)

    return entries


def parse_philpapers_result(data: dict, source_file: str) -> list[SourceMetadata]:
    """Parse PhilPapers JSON format."""
    results = data.get("results", [])
    entries = []

    for item in results:
        entry = SourceMetadata(
            doi=None,  # PhilPapers doesn't always provide DOI
            title=item.get("title", ""),
            container_title=item.get("journal") or item.get("source"),
            volume=item.get("volume"),
            issue=item.get("issue"),
            pages=item.get("pages"),
            publisher=item.get("publisher"),
            year=item.get("year"),
            source_file=source_file,
            source_api="philpapers"
        )
        entries.append(entry)

    return entries


def detect_api_source(data: dict, filename: str) -> str:
    """Detect which API produced this JSON file."""
    source = data.get("source", "").lower()

    if "semantic_scholar" in source or "s2" in source:
        return "s2"
    elif "openalex" in source:
        return "openalex"
    elif "crossref" in source:
        return "crossref"
    elif "arxiv" in source:
        return "arxiv"
    elif "philpapers" in source:
        return "philpapers"

    # Fallback: detect from filename
    fname = filename.lower()
    if "s2_" in fname or fname.startswith("s2"):
        return "s2"
    elif "openalex" in fname or "oa_" in fname:
        return "openalex"
    elif "crossref" in fname:
        return "crossref"
    elif "arxiv" in fname:
        return "arxiv"
    elif "philpapers" in fname or "pp_" in fname:
        return "philpapers"

    return "unknown"


def build_metadata_index(json_dir: Path) -> MetadataIndex:
    """Build index of all metadata from JSON files in directory."""
    index = MetadataIndex()

    if not json_dir.exists():
        return index

    for json_file in json_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        # Detect source and parse accordingly
        api_source = detect_api_source(data, json_file.name)

        if api_source == "s2":
            entries = parse_s2_result(data, json_file.name)
        elif api_source == "openalex":
            entries = parse_openalex_result(data, json_file.name)
        elif api_source == "crossref":
            entries = parse_crossref_result(data, json_file.name)
        elif api_source == "arxiv":
            entries = parse_arxiv_result(data, json_file.name)
        elif api_source == "philpapers":
            entries = parse_philpapers_result(data, json_file.name)
        else:
            # Try S2 format as default (most common)
            entries = parse_s2_result(data, json_file.name)

        # Add entries to index
        for entry in entries:
            index.entries.append(entry)

            # Index journal/container title
            if entry.container_title:
                norm = normalize_journal(entry.container_title)
                if norm not in index.journals:
                    index.journals[norm] = []
                index.journals[norm].append((entry.container_title, entry.source_file))

            # Index volume
            if entry.volume:
                vol = str(entry.volume).strip()
                if vol not in index.volumes:
                    index.volumes[vol] = []
                index.volumes[vol].append(entry.source_file)

            # Index issue
            if entry.issue:
                iss = str(entry.issue).strip()
                if iss not in index.issues:
                    index.issues[iss] = []
                index.issues[iss].append(entry.source_file)

            # Index pages
            if entry.pages:
                norm = normalize_pages(entry.pages)
                if norm not in index.pages:
                    index.pages[norm] = []
                index.pages[norm].append((entry.pages, entry.source_file))

            # Index publisher
            if entry.publisher:
                pub = entry.publisher.lower().strip()
                if pub not in index.publishers:
                    index.publishers[pub] = []
                index.publishers[pub].append((entry.publisher, entry.source_file))

            # Index year
            if entry.year:
                yr = str(entry.year)
                if yr not in index.years:
                    index.years[yr] = []
                index.years[yr].append(entry.source_file)

            # Index DOI
            if entry.doi:
                norm = normalize_doi(entry.doi)
                index.dois[norm] = entry.source_file

    return index


@dataclass
class ValidationError:
    """A single validation error."""
    entry_key: str
    field_name: str
    bibtex_value: str
    api_values: list[str]  # What the API actually has
    message: str


def validate_entry(entry_key: str, entry, index: MetadataIndex) -> list[ValidationError]:
    """Validate a single BibTeX entry against the metadata index."""
    errors = []
    fields = entry.fields

    # Check journal/booktitle
    for field_name in ['journal', 'booktitle']:
        if field_name in fields:
            value = fields[field_name]
            norm = normalize_journal(value)
            if norm not in index.journals:
                # Collect all journal names from API output
                api_journals = list(set(
                    orig for values in index.journals.values() for orig, _ in values
                ))[:5]
                if not api_journals:
                    api_journals = ["(no journal data in API output)"]
                errors.append(ValidationError(
                    entry_key=entry_key,
                    field_name=field_name,
                    bibtex_value=value,
                    api_values=api_journals,
                    message=f"'{field_name}' value not found in API output"
                ))

    # Check volume
    if 'volume' in fields:
        value = str(fields['volume']).strip()
        if value not in index.volumes:
            errors.append(ValidationError(
                entry_key=entry_key,
                field_name='volume',
                bibtex_value=value,
                api_values=list(index.volumes.keys())[:10],
                message="'volume' value not found in API output"
            ))

    # Check number/issue
    if 'number' in fields:
        value = str(fields['number']).strip()
        if value not in index.issues:
            errors.append(ValidationError(
                entry_key=entry_key,
                field_name='number',
                bibtex_value=value,
                api_values=list(index.issues.keys())[:10] if index.issues else ["(no issue data in API output)"],
                message="'number' value not found in API output"
            ))

    # Check pages
    if 'pages' in fields:
        value = fields['pages']
        norm = normalize_pages(value)
        if norm not in index.pages:
            errors.append(ValidationError(
                entry_key=entry_key,
                field_name='pages',
                bibtex_value=value,
                api_values=[orig for values in index.pages.values() for orig, _ in values][:10],
                message="'pages' value not found in API output"
            ))

    # Check publisher
    if 'publisher' in fields:
        value = fields['publisher']
        norm = value.lower().strip()
        if norm not in index.publishers:
            errors.append(ValidationError(
                entry_key=entry_key,
                field_name='publisher',
                bibtex_value=value,
                api_values=[orig for values in index.publishers.values() for orig, _ in values][:5] or ["(no publisher data in API output)"],
                message="'publisher' value not found in API output"
            ))

    # Check year (lenient - just verify it exists somewhere)
    if 'year' in fields:
        value = str(fields['year']).strip()
        if value not in index.years:
            errors.append(ValidationError(
                entry_key=entry_key,
                field_name='year',
                bibtex_value=value,
                api_values=list(index.years.keys())[:10],
                message="'year' value not found in API output"
            ))

    # Check DOI (if present, should match)
    if 'doi' in fields:
        value = fields['doi']
        norm = normalize_doi(value)
        if norm and norm not in index.dois:
            errors.append(ValidationError(
                entry_key=entry_key,
                field_name='doi',
                bibtex_value=value,
                api_values=list(index.dois.keys())[:5] or ["(no DOI data in API output)"],
                message="'doi' value not found in API output"
            ))

    return errors


def validate_metadata(bib_path: Path, json_dir: Path, mode: str = "strict") -> dict:
    """Validate BibTeX metadata against JSON API output.

    Args:
        bib_path: Path to BibTeX file
        json_dir: Path to directory containing JSON API output files
        mode: "strict" (block on errors) or "warn" (report but don't fail)

    Returns:
        {"valid": bool, "errors": list[str], "verified_count": int, "error_count": int}
    """
    result = {
        "valid": True,
        "errors": [],
        "verified_count": 0,
        "error_count": 0,
        "warnings": []
    }

    # Check files exist
    if not bib_path.exists():
        result["valid"] = False
        result["errors"].append(f"BibTeX file not found: {bib_path}")
        return result

    if not json_dir.exists():
        result["warnings"].append(f"JSON directory not found: {json_dir} - skipping metadata validation")
        return result

    # Build metadata index from JSON files
    index = build_metadata_index(json_dir)

    if not index.entries:
        result["warnings"].append("No API results found in JSON directory - skipping metadata validation")
        return result

    # Parse BibTeX file
    try:
        bib_data = parse_file(str(bib_path), bib_format='bibtex')
    except PybtexSyntaxError as e:
        result["valid"] = False
        result["errors"].append(f"BibTeX syntax error: {e}")
        return result
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"BibTeX parsing error: {e}")
        return result

    # Validate each entry
    all_errors = []
    for key, entry in bib_data.entries.items():
        entry_errors = validate_entry(key, entry, index)
        all_errors.extend(entry_errors)

        if entry_errors:
            result["error_count"] += 1
        else:
            result["verified_count"] += 1

    # Format error messages
    if all_errors:
        result["errors"].append("METADATA VALIDATION FAILED\n")

        # Group errors by entry
        errors_by_entry = {}
        for err in all_errors:
            if err.entry_key not in errors_by_entry:
                errors_by_entry[err.entry_key] = []
            errors_by_entry[err.entry_key].append(err)

        for entry_key, errs in errors_by_entry.items():
            result["errors"].append(f"Entry: {entry_key}")
            for err in errs:
                result["errors"].append(f"  - Field '{err.field_name}' = \"{err.bibtex_value}\"")
                result["errors"].append(f"    NOT FOUND in API output.")
                if err.api_values and err.api_values[0] != "(no" and not err.api_values[0].startswith("(no"):
                    result["errors"].append(f"    API sources contain: {', '.join(err.api_values[:3])}")
                result["errors"].append(f"    Action: Remove field or use value from API output\n")

        result["errors"].append(f"{len(errors_by_entry)} entries have unverifiable metadata fields.")

        if mode == "strict":
            result["valid"] = False

    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "valid": False,
            "errors": ["Usage: python metadata_validator.py <bib_file> <json_dir> [--mode=strict|warn]"]
        }))
        sys.exit(2)

    bib_path = Path(sys.argv[1])
    json_dir = Path(sys.argv[2])

    # Parse mode argument
    mode = "strict"
    for arg in sys.argv[3:]:
        if arg.startswith("--mode="):
            mode = arg.split("=")[1]

    result = validate_metadata(bib_path, json_dir, mode)
    print(json.dumps(result, indent=2))

    if not result["valid"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
