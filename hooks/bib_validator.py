#!/usr/bin/env python3
"""BibTeX validator for SubagentStop hook.

Validates .bib files for:
1. UTF-8 encoding
2. No LaTeX diacritic escapes
3. Valid BibTeX syntax
4. No duplicate keys
5. Required fields per entry type
6. No BibLaTeX fields

Usage: python bib_validator.py <path>
Output: JSON to stdout
Exit codes: 0 = valid, 1 = validation errors, 2 = file not found/read error
"""

import json
import re
import sys
from pathlib import Path

from pybtex.database import parse_file
from pybtex.database.input.bibtex import Parser
from pybtex.scanner import PybtexSyntaxError


# LaTeX diacritic escapes and their Unicode replacements
LATEX_ESCAPES = {
    r'\"a': 'ä', r'\"e': 'ë', r'\"i': 'ï', r'\"o': 'ö', r'\"u': 'ü',
    r'\"A': 'Ä', r'\"E': 'Ë', r'\"I': 'Ï', r'\"O': 'Ö', r'\"U': 'Ü',
    r"\'a": 'á', r"\'e": 'é', r"\'i": 'í', r"\'o": 'ó', r"\'u": 'ú',
    r"\'A": 'Á', r"\'E": 'É', r"\'I": 'Í', r"\'O": 'Ó', r"\'U": 'Ú',
    r'\`a': 'à', r'\`e': 'è', r'\`i': 'ì', r'\`o': 'ò', r'\`u': 'ù',
    r'\`A': 'À', r'\`E': 'È', r'\`I': 'Ì', r'\`O': 'Ò', r'\`U': 'Ù',
    r'\^a': 'â', r'\^e': 'ê', r'\^i': 'î', r'\^o': 'ô', r'\^u': 'û',
    r'\^A': 'Â', r'\^E': 'Ê', r'\^I': 'Î', r'\^O': 'Ô', r'\^U': 'Û',
    r'\~a': 'ã', r'\~n': 'ñ', r'\~o': 'õ',
    r'\~A': 'Ã', r'\~N': 'Ñ', r'\~O': 'Õ',
    r'\c{c}': 'ç', r'\c{C}': 'Ç',
    r'\ss': 'ß', r'{\ss}': 'ß',
    r'\o': 'ø', r'\O': 'Ø',
    r'\aa': 'å', r'\AA': 'Å',
    r'\ae': 'æ', r'\AE': 'Æ',
    r'\oe': 'œ', r'\OE': 'Œ',
    r'\l': 'ł', r'\L': 'Ł',
}

# Pattern to match LaTeX diacritic commands
# Matches: {\"a}, \"a, {\'e}, \'e, {\~n}, \~n, \c{c}, {\ss}, \ss, etc.
LATEX_ESCAPE_PATTERN = re.compile(
    r'\{?\\["\'`^~]([aeiouAEIOU])\}?'  # accent commands
    r'|\{?\\c\{([cC])\}\}?'  # cedilla
    r'|\{?\\ss\}?'  # eszett
    r'|\{?\\([oO]|aa|AA|ae|AE|oe|OE|[lL])\}?'  # special letters
)

# Required fields by entry type
REQUIRED_FIELDS = {
    'article': {'author', 'title', 'journal', 'year'},
    'book': {'title', 'publisher', 'year'},  # author OR editor
    'inproceedings': {'author', 'title', 'booktitle', 'year'},
    'incollection': {'author', 'title', 'booktitle', 'publisher', 'year'},
    'phdthesis': {'author', 'title', 'school', 'year'},
    'mastersthesis': {'author', 'title', 'school', 'year'},
    'techreport': {'author', 'title', 'institution', 'year'},
    'misc': {'author', 'title', 'year'},
}

# BibLaTeX fields that should be converted to BibTeX equivalents
BIBLATEX_FIELDS = {
    'journaltitle': 'journal',
    'date': 'year',
    'location': 'address',
}


def check_utf8_encoding(path):
    """Check 1: Verify file is valid UTF-8."""
    errors = []
    try:
        with open(path, 'r', encoding='utf-8', errors='strict') as f:
            f.read()
    except UnicodeDecodeError as e:
        errors.append(f"Invalid UTF-8 encoding at byte position {e.start}: {e.reason}")
    return errors


def check_latex_escapes(path, content):
    """Check 2: Find LaTeX diacritic escapes and suggest Unicode replacements."""
    errors = []
    lines = content.split('\n')

    # Track which entry we're in for better error messages
    current_key = None
    current_field = None

    # Define patterns with their replacement lookups
    # Each tuple: (regex pattern, function to get replacement from match)
    patterns = [
        # Accent commands: {\"a}, \"a, {\'e}, \'e, etc.
        (r'\{\\(["\'])\s*([aeiouAEIOU])\}', lambda m: LATEX_ESCAPES.get(f'\\{m.group(1)}{m.group(2)}', '?')),
        (r'(?<!\{)\\(["\'])\s*([aeiouAEIOU])(?!\})', lambda m: LATEX_ESCAPES.get(f'\\{m.group(1)}{m.group(2)}', '?')),
        # Grave accent: {\`a}, \`a
        (r'\{\\`([aeiouAEIOU])\}', lambda m: LATEX_ESCAPES.get(f'\\`{m.group(1)}', '?')),
        (r'(?<!\{)\\`([aeiouAEIOU])(?!\})', lambda m: LATEX_ESCAPES.get(f'\\`{m.group(1)}', '?')),
        # Circumflex: {\^a}, \^a
        (r'\{\\\^([aeiouAEIOU])\}', lambda m: LATEX_ESCAPES.get(f'\\^{m.group(1)}', '?')),
        (r'(?<!\{)\\\^([aeiouAEIOU])(?!\})', lambda m: LATEX_ESCAPES.get(f'\\^{m.group(1)}', '?')),
        # Tilde: {\~n}, \~n
        (r'\{\\~([anoANO])\}', lambda m: LATEX_ESCAPES.get(f'\\~{m.group(1)}', '?')),
        (r'(?<!\{)\\~([anoANO])(?!\})', lambda m: LATEX_ESCAPES.get(f'\\~{m.group(1)}', '?')),
        # Cedilla: \c{c}
        (r'\\c\{([cC])\}', lambda m: LATEX_ESCAPES.get(f'\\c{{{m.group(1)}}}', '?')),
        # Eszett: {\ss}, \ss
        (r'\{\\ss\}', lambda m: 'ß'),
        (r'(?<!\{)\\ss(?!\})', lambda m: 'ß'),
        # Multi-char special letters (must come before single-char): \aa, \ae, \oe, \AA, \AE, \OE
        (r'\{\\(aa|AA|ae|AE|oe|OE)\}', lambda m: LATEX_ESCAPES.get(f'\\{m.group(1)}', '?')),
        (r'(?<!\{)\\(aa|AA|ae|AE|oe|OE)(?![a-zA-Z])', lambda m: LATEX_ESCAPES.get(f'\\{m.group(1)}', '?')),
        # Single-char special letters: \o, \O, \l, \L
        (r'\{\\([oOlL])\}', lambda m: LATEX_ESCAPES.get(f'\\{m.group(1)}', '?')),
        (r'(?<!\{)\\([oOlL])(?![a-zA-Z])', lambda m: LATEX_ESCAPES.get(f'\\{m.group(1)}', '?')),
    ]

    for line_num, line in enumerate(lines, 1):
        # Track entry key
        entry_match = re.match(r'@\w+\{([^,]+),', line)
        if entry_match:
            current_key = entry_match.group(1).strip()

        # Track field name
        field_match = re.match(r'\s*(\w+)\s*=', line)
        if field_match:
            current_field = field_match.group(1)

        # Check all patterns
        for pattern, get_replacement in patterns:
            for match in re.finditer(pattern, line):
                escape = match.group(0)
                replacement = get_replacement(match)
                location = f"{current_key}: '{current_field}'" if current_key else f"line {line_num}"
                errors.append(f"{location} contains LaTeX escape {escape} — replace with {replacement}")

    return errors


def check_duplicate_fields(content):
    """Check 4b: Find duplicate field names within entries (before pybtex parsing).

    Detects entries with repeated field names (e.g., two `note` fields),
    which is invalid BibTeX. Returns clear errors with entry keys and line numbers.

    Uses brace-depth tracking to avoid false positives from multi-line field
    values that happen to contain 'word = text' patterns.
    """
    errors = []
    lines = content.split('\n')

    current_key = None
    fields_seen = {}  # field_name -> line_number
    # brace_depth tracks nesting: 0 = between entries, 1 = inside entry
    # (at top level between fields), 2+ = inside a field value
    brace_depth = 0
    in_comment = False

    for line_num, line in enumerate(lines, 1):
        # Detect entry start
        entry_match = re.match(r'@(\w+)\{', line, re.IGNORECASE)
        if entry_match and brace_depth == 0:
            entry_type = entry_match.group(1).lower()
            if entry_type == 'comment':
                in_comment = True
                # Count braces in this line for comment blocks
                brace_depth += line.count('{') - line.count('}')
                continue
            # Extract key from the rest: @type{key, ...
            rest = line[entry_match.end():]
            key_match = re.match(r'([^,]+),', rest)
            if key_match:
                current_key = key_match.group(1).strip()
                fields_seen = {}
                # Count braces: the opening { from @type{ is already +1
                brace_depth = line.count('{') - line.count('}')
                # Check for fields on the same line after the key
                after_key = rest[key_match.end():]
                field_on_line = re.match(r'\s*(\w+)\s*=\s*', after_key)
                if field_on_line:
                    fields_seen[field_on_line.group(1).lower()] = line_num
            continue

        if in_comment:
            brace_depth += line.count('{') - line.count('}')
            if brace_depth <= 0:
                in_comment = False
                brace_depth = 0
            continue

        if current_key is None:
            continue

        # Only detect fields when at entry top level (brace_depth == 1)
        # This avoids false positives from text inside multi-line field values
        if brace_depth == 1:
            field_match = re.match(r'\s*(\w+)\s*=\s*', line)
            if field_match:
                field_name = field_match.group(1).lower()
                if field_name in fields_seen:
                    errors.append(
                        f"{current_key}: duplicate field '{field_name}' "
                        f"(first on line {fields_seen[field_name]}, duplicate on line {line_num})"
                    )
                else:
                    fields_seen[field_name] = line_num

        # Update brace depth
        brace_depth += line.count('{') - line.count('}')

        # Entry ended
        if brace_depth <= 0:
            current_key = None
            fields_seen = {}
            brace_depth = 0

    return errors


def check_duplicate_keys(content):
    """Check 4: Find duplicate citation keys (before pybtex parsing silently overwrites)."""
    errors = []
    keys = {}
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        match = re.match(r'@\w+\{([^,]+),', line, re.IGNORECASE)
        if match:
            key = match.group(1).strip()
            if key.lower() == 'comment':
                continue
            if key in keys:
                errors.append(
                    f"{key}: duplicate citation key (first occurrence line {keys[key]}, duplicate line {line_num})"
                )
            else:
                keys[key] = line_num

    return errors


def check_bibtex_syntax(path):
    """Check 3: Verify BibTeX syntax is valid."""
    errors = []
    try:
        parse_file(path, bib_format='bibtex')
    except PybtexSyntaxError as e:
        errors.append(f"BibTeX syntax error: {e}")
    except Exception as e:
        errors.append(f"BibTeX parsing error: {e}")
    return errors


def check_required_fields(path):
    """Check 5: Verify required fields are present for each entry type."""
    errors = []
    try:
        bib_data = parse_file(path, bib_format='bibtex')
        for key, entry in bib_data.entries.items():
            entry_type = entry.type.lower()
            if entry_type not in REQUIRED_FIELDS:
                continue

            required = REQUIRED_FIELDS[entry_type]
            present = set(entry.fields.keys())

            # Add persons fields (author, editor)
            if entry.persons.get('author'):
                present.add('author')
            if entry.persons.get('editor'):
                present.add('editor')

            # Special case: book requires author OR editor
            if entry_type == 'book':
                if 'author' not in present and 'editor' not in present:
                    errors.append(f"{key}: missing required field 'author' or 'editor' for @book")
                missing = required - present - {'author'}  # remove author since we checked it specially
            else:
                missing = required - present

            for field in sorted(missing):
                errors.append(f"{key}: missing required field '{field}' for @{entry_type}")
    except Exception:
        pass  # Syntax errors already caught in check_bibtex_syntax

    return errors


def check_biblatex_fields(path):
    """Check 6: Flag BibLaTeX-specific fields that should use BibTeX equivalents."""
    errors = []
    try:
        bib_data = parse_file(path, bib_format='bibtex')
        for key, entry in bib_data.entries.items():
            for biblatex_field, bibtex_field in BIBLATEX_FIELDS.items():
                if biblatex_field in entry.fields:
                    errors.append(
                        f"{key}: BibLaTeX field '{biblatex_field}' found — use '{bibtex_field}' instead"
                    )
    except Exception:
        pass  # Syntax errors already caught in check_bibtex_syntax

    return errors


def validate_bib(path):
    """Run all validation checks on a BibTeX file.

    Returns: {"valid": bool, "errors": list[str]}
    """
    path = Path(path)
    errors = []

    # Check file exists
    if not path.exists():
        return {"valid": False, "errors": [f"File not found: {path}"]}

    # Check 1: UTF-8 encoding
    utf8_errors = check_utf8_encoding(path)
    errors.extend(utf8_errors)

    # If UTF-8 check failed, we can't reliably read the file for other checks
    if utf8_errors:
        return {"valid": False, "errors": errors}

    # Read file content for checks that need raw content
    content = path.read_text(encoding='utf-8')

    # Check 2: LaTeX escapes
    errors.extend(check_latex_escapes(path, content))

    # Check 4: Duplicate keys (before pybtex parsing)
    errors.extend(check_duplicate_keys(content))

    # Check 4b: Duplicate fields within entries (before pybtex parsing)
    errors.extend(check_duplicate_fields(content))

    # Check 3: BibTeX syntax
    syntax_errors = check_bibtex_syntax(path)
    errors.extend(syntax_errors)

    # Only run field checks if syntax is valid
    if not syntax_errors:
        # Check 5: Required fields
        errors.extend(check_required_fields(path))

        # Check 6: BibLaTeX fields
        errors.extend(check_biblatex_fields(path))

    return {"valid": len(errors) == 0, "errors": errors}


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"valid": False, "errors": ["Usage: python bib_validator.py <path>"]}))
        sys.exit(2)

    path = sys.argv[1]
    result = validate_bib(path)
    print(json.dumps(result, indent=2))

    if not result["valid"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
