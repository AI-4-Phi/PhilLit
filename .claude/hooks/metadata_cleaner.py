#!/usr/bin/env python3
"""Metadata provenance cleaner for SubagentStop hook.

Removes BibTeX bibliographic metadata that cannot be verified against API output,
preventing hallucinated data from persisting in the bibliography.

This is the "fix" counterpart to metadata_validator.py - instead of blocking,
it automatically removes unverifiable fields while preserving verified data.

Features:
1. Removes unverifiable fields (journal, booktitle, volume, number, pages, publisher, doi)
2. Corrects year from API data via DOI lookup when mismatched
3. Downgrades entry types to @misc when required fields are removed
4. Tags cleaned entries with METADATA_CLEANED in keywords field

Preserved fields (never removed):
- author, title (identity fields - entry is meaningless without them)
- year (corrected rather than removed, via DOI lookup)
- note, keywords, abstract_source, howpublished, url, abstract (LLM-generated)

Usage: python metadata_cleaner.py <bib_file> <json_dir>
Output: JSON to stdout with cleaning summary
Exit codes: 0 = success, 2 = file not found/read error
"""

import json
import re


import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pybtex.database import parse_file, BibliographyData
from pybtex.database.output.bibtex import Writer
from pybtex.scanner import PybtexSyntaxError


# Fields that should be cleaned if not verifiable
CLEANABLE_FIELDS = {
    'journal', 'booktitle', 'volume', 'number', 'pages', 'publisher', 'doi'
}

# Fields exempt from cleaning (LLM-generated content is OK)
EXEMPT_FIELDS = {
    'note', 'keywords', 'abstract_source', 'howpublished', 'url', 'abstract'
}

# Identity fields - never remove these (entry is meaningless without them)
IDENTITY_FIELDS = {'author', 'title'}

# Correctable fields - can be updated from API data rather than removed
CORRECTABLE_FIELDS = {'year'}

# Required fields by entry type - if missing after cleaning, downgrade to @misc
REQUIRED_FIELDS = {
    'article': {'journal'},
    'incollection': {'booktitle', 'publisher'},
    'inproceedings': {'booktitle'},
    'book': {'publisher'},
    'inbook': {'publisher'},
    'phdthesis': {'school'},
    'mastersthesis': {'school'},
    'techreport': {'institution'},
}


@dataclass
class MetadataIndex:
    """Index of all metadata values from JSON files."""
    journals: dict = field(default_factory=dict)
    volumes: dict = field(default_factory=dict)
    issues: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    publishers: dict = field(default_factory=dict)
    years: dict = field(default_factory=dict)
    dois: dict = field(default_factory=dict)
    entries: list = field(default_factory=list)


def normalize_pages(pages: str) -> str:
    """Normalize page ranges for comparison."""
    if not pages:
        return ""
    normalized = re.sub(r'\s*[-–—]+\s*', '-', str(pages))
    return normalized.strip()


def normalize_journal(name: str) -> str:
    """Normalize journal name for comparison."""
    if not name:
        return ""
    normalized = name.lower().strip()
    if normalized.startswith("the "):
        normalized = normalized[4:]
    normalized = " ".join(normalized.split())
    return normalized


def normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    if not doi:
        return ""
    doi = doi.strip().lower()
    prefixes = ["https://doi.org/", "http://doi.org/", "doi:", "doi.org/"]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def find_api_entry_by_doi(doi: str, index: 'MetadataIndex') -> Optional[dict]:
    """Find the API entry that matches the given DOI."""
    if not doi:
        return None
    norm_doi = normalize_doi(doi)
    for api_entry in index.entries:
        api_doi = api_entry.get("doi")
        if api_doi and normalize_doi(api_doi) == norm_doi:
            return api_entry
    return None


def should_downgrade_to_misc(entry) -> bool:
    """Check if entry should be downgraded due to missing required fields."""
    entry_type = entry.type.lower()
    if entry_type not in REQUIRED_FIELDS:
        return False
    required = REQUIRED_FIELDS[entry_type]
    present_fields = {f.lower() for f in entry.fields.keys()}
    return not required.issubset(present_fields)


def parse_s2_result(data: dict, source_file: str) -> list[dict]:
    """Parse Semantic Scholar JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        journal_info = item.get("journal") or {}
        entries.append({
            "container_title": journal_info.get("name") or item.get("venue"),
            "volume": str(journal_info.get("volume")) if journal_info.get("volume") else None,
            "issue": None,
            "pages": journal_info.get("pages"),
            "publisher": None,
            "year": item.get("year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_openalex_result(data: dict, source_file: str) -> list[dict]:
    """Parse OpenAlex JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        source = item.get("source") or {}
        entries.append({
            "container_title": source.get("name"),
            "volume": None,
            "issue": None,
            "pages": None,
            "publisher": None,
            "year": item.get("publication_year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_crossref_result(data: dict, source_file: str) -> list[dict]:
    """Parse CrossRef JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        entries.append({
            "container_title": item.get("container_title"),
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("page"),
            "publisher": item.get("publisher"),
            "year": item.get("year"),
            "doi": item.get("doi"),
        })
    return entries


def parse_arxiv_result(data: dict, source_file: str) -> list[dict]:
    """Parse arXiv JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        year = None
        if item.get("published"):
            try:
                year = int(item["published"][:4])
            except (ValueError, TypeError):
                pass
        entries.append({
            "container_title": item.get("journal_ref"),
            "volume": None,
            "issue": None,
            "pages": None,
            "publisher": None,
            "year": year,
            "doi": item.get("doi"),
        })
    return entries


def parse_philpapers_result(data: dict, source_file: str) -> list[dict]:
    """Parse PhilPapers JSON format."""
    results = data.get("results", [])
    entries = []
    for item in results:
        entries.append({
            "container_title": item.get("journal") or item.get("source"),
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("pages"),
            "publisher": item.get("publisher"),
            "year": item.get("year"),
            "doi": None,
        })
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

    fname = filename.lower()
    if "s2_" in fname or fname.startswith("s2"):
        return "s2"
    elif "openalex" in fname or "oa_" in fname:
        return "openalex"
    elif "crossref" in fname or "verify_" in fname:
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
            entries = parse_s2_result(data, json_file.name)

        for entry in entries:
            index.entries.append(entry)

            if entry.get("container_title"):
                norm = normalize_journal(entry["container_title"])
                if norm not in index.journals:
                    index.journals[norm] = []
                index.journals[norm].append(entry["container_title"])

            if entry.get("volume"):
                vol = str(entry["volume"]).strip()
                if vol not in index.volumes:
                    index.volumes[vol] = []
                index.volumes[vol].append(json_file.name)

            if entry.get("issue"):
                iss = str(entry["issue"]).strip()
                if iss not in index.issues:
                    index.issues[iss] = []
                index.issues[iss].append(json_file.name)

            if entry.get("pages"):
                norm = normalize_pages(entry["pages"])
                if norm not in index.pages:
                    index.pages[norm] = []
                index.pages[norm].append(entry["pages"])

            if entry.get("publisher"):
                pub = entry["publisher"].lower().strip()
                if pub not in index.publishers:
                    index.publishers[pub] = []
                index.publishers[pub].append(entry["publisher"])

            if entry.get("year"):
                yr = str(entry["year"])
                if yr not in index.years:
                    index.years[yr] = []
                index.years[yr].append(json_file.name)

            if entry.get("doi"):
                norm = normalize_doi(entry["doi"])
                index.dois[norm] = json_file.name

    return index


def is_field_verifiable(field_name: str, value: str, index: MetadataIndex) -> bool:
    """Check if a field value can be verified against the metadata index."""
    if field_name in ('journal', 'booktitle'):
        norm = normalize_journal(value)
        return norm in index.journals

    elif field_name == 'volume':
        return str(value).strip() in index.volumes

    elif field_name == 'number':
        return str(value).strip() in index.issues

    elif field_name == 'pages':
        norm = normalize_pages(value)
        return norm in index.pages

    elif field_name == 'publisher':
        return value.lower().strip() in index.publishers

    elif field_name == 'doi':
        norm = normalize_doi(value)
        return norm in index.dois

    # Unknown field - assume verifiable (don't remove)
    return True


def clean_entry(entry_key: str, entry, index: MetadataIndex) -> dict:
    """Clean unverifiable fields from a single BibTeX entry.

    Returns dict with:
        - removed_fields: list of removed field descriptions (e.g., "volume=99")
        - year_corrected: tuple (old, new) if corrected, None otherwise
        - type_downgraded: tuple (old, new) if downgraded, None otherwise
    """
    result = {
        "removed_fields": [],
        "year_corrected": None,
        "type_downgraded": None,
    }

    # Step 1: Year correction via DOI lookup
    doi_value = entry.fields.get('doi')
    if doi_value:
        api_entry = find_api_entry_by_doi(doi_value, index)
        if api_entry and api_entry.get("year"):
            api_year = str(api_entry["year"])
            bib_year = entry.fields.get('year', '')
            if bib_year and bib_year != api_year:
                entry.fields['year'] = api_year
                result["year_corrected"] = (bib_year, api_year)

    # Step 2: Remove unverifiable fields
    fields_to_remove = []
    for field_name in list(entry.fields.keys()):
        field_lower = field_name.lower()
        # Skip identity, exempt, and correctable fields
        if field_lower in IDENTITY_FIELDS or field_lower in EXEMPT_FIELDS or field_lower in CORRECTABLE_FIELDS:
            continue

        # Only clean fields we're configured to clean
        if field_lower not in CLEANABLE_FIELDS:
            continue

        value = entry.fields[field_name]

        if not is_field_verifiable(field_lower, value, index):
            fields_to_remove.append(field_name)
            result["removed_fields"].append(f"{field_name}={value}")

    for field_name in fields_to_remove:
        del entry.fields[field_name]

    # Step 3: Entry type downgrade check
    if should_downgrade_to_misc(entry):
        old_type = entry.type
        entry.type = 'misc'
        entry.original_type = 'misc'  # pybtex Writer uses original_type
        result["type_downgraded"] = (old_type, 'misc')

    # Step 4: Add tag to indicate cleaning was performed
    all_changes = []
    if result["removed_fields"]:
        # Extract just field names from "field=value" format
        all_changes.extend([f.split('=')[0] for f in result["removed_fields"]])
    if result["year_corrected"]:
        old_yr, new_yr = result["year_corrected"]
        all_changes.append(f"year:{old_yr}->{new_yr}")
    if result["type_downgraded"]:
        old_type, new_type = result["type_downgraded"]
        all_changes.append(f"type:@{old_type}->@{new_type}")

    if all_changes:
        cleaned_tag = f"METADATA_CLEANED: {', '.join(all_changes)}"
        if 'keywords' in entry.fields:
            entry.fields['keywords'] += f", {cleaned_tag}"
        else:
            entry.fields['keywords'] = cleaned_tag

    return result


def write_bibtex(bib_data: BibliographyData, output_path: Path) -> None:
    """Write BibliographyData to file with consistent formatting."""
    writer = Writer()
    with open(output_path, 'w', encoding='utf-8') as f:
        writer.write_file(bib_data, f)


def clean_bibtex(bib_path: Path, json_dir: Path) -> dict:
    """Clean unverifiable metadata from BibTeX file.

    Args:
        bib_path: Path to BibTeX file
        json_dir: Path to directory containing JSON API output files

    Returns:
        {"success": bool, "cleaned_entries": dict, "total_fields_removed": int,
         "years_corrected": int, "types_downgraded": int, "errors": list}
    """
    result = {
        "success": True,
        "cleaned_entries": {},  # entry_key -> [removed fields]
        "total_fields_removed": 0,
        "years_corrected": 0,
        "types_downgraded": 0,
        "entries_cleaned": 0,
        "entries_total": 0,
        "errors": [],
        "warnings": []
    }

    # Check files exist
    if not bib_path.exists():
        result["success"] = False
        result["errors"].append(f"BibTeX file not found: {bib_path}")
        return result

    if not json_dir.exists():
        result["warnings"].append(f"JSON directory not found: {json_dir} - skipping cleaning")
        return result

    # Build metadata index
    index = build_metadata_index(json_dir)

    if not index.entries:
        result["warnings"].append("No API results found in JSON directory - skipping cleaning")
        return result

    # Parse BibTeX file
    try:
        bib_data = parse_file(str(bib_path), bib_format='bibtex')
    except PybtexSyntaxError as e:
        result["success"] = False
        result["errors"].append(f"BibTeX syntax error: {e}")
        return result
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"BibTeX parsing error: {e}")
        return result

    result["entries_total"] = len(bib_data.entries)

    # Clean each entry
    any_changes = False
    for entry_key, entry in bib_data.entries.items():
        entry_result = clean_entry(entry_key, entry, index)

        # Check if any changes were made to this entry
        entry_changed = (
            entry_result["removed_fields"] or
            entry_result["year_corrected"] or
            entry_result["type_downgraded"]
        )

        if entry_changed:
            any_changes = True
            result["entries_cleaned"] += 1
            # Store removed fields for backwards compatibility
            result["cleaned_entries"][entry_key] = entry_result["removed_fields"]
            result["total_fields_removed"] += len(entry_result["removed_fields"])

            if entry_result["year_corrected"]:
                result["years_corrected"] += 1
            if entry_result["type_downgraded"]:
                result["types_downgraded"] += 1

    # Write cleaned BibTeX back
    if any_changes:
        write_bibtex(bib_data, bib_path)

    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "success": False,
            "errors": ["Usage: python metadata_cleaner.py <bib_file> <json_dir>"]
        }))
        sys.exit(2)

    bib_path = Path(sys.argv[1])
    json_dir = Path(sys.argv[2])

    result = clean_bibtex(bib_path, json_dir)
    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
