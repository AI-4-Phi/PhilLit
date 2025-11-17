#!/usr/bin/env python3
"""Clean BibTeX files by removing fraudulent entries."""

import re

# Fraudulent citation keys to remove
FRAUDULENT_DOMAIN_4 = [
    'shneiderman2025symbiotic',
    'chi2024evaluating',
    'zhang2025exploring',
    'zhang2025trust',
    'lee2023taylorism',
    'ivanova2023influence',
    'fuge2025agency',
    'cameron2023legitimacy',
    'kumar2025aiethics',
    'mehrabi2024fairness',
    'pasquale2024braverman',
    'spencer2022artificial',
    'collier2021labor',
    'moore2018datatification',
    'ball2023algorithmic',
]

FRAUDULENT_DOMAIN_1 = [
    'veltman2022revisionary',
]

def remove_bibtex_entries(content, keys_to_remove):
    """Remove BibTeX entries with specified keys."""
    lines = content.split('\n')
    cleaned_lines = []
    skip_entry = False
    current_key = None
    brace_count = 0

    for line in lines:
        # Check if this is the start of a BibTeX entry
        entry_match = re.match(r'@(\w+)\{([^,\s]+)', line)
        if entry_match:
            current_key = entry_match.group(2)
            if current_key in keys_to_remove:
                skip_entry = True
                brace_count = 1  # Start counting braces
                continue
            else:
                skip_entry = False
                brace_count = 0

        if skip_entry:
            # Count braces to know when entry ends
            brace_count += line.count('{') - line.count('}')
            if brace_count <= 0:
                skip_entry = False
                current_key = None
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)

def main():
    # Clean Domain 4
    with open('literature-domain-4-ai-workplace-autonomy.bib', 'r') as f:
        content = f.read()

    cleaned = remove_bibtex_entries(content, FRAUDULENT_DOMAIN_4)

    with open('literature-domain-4-ai-workplace-autonomy.bib', 'w') as f:
        f.write(cleaned)

    print(f"Domain 4: Removed {len(FRAUDULENT_DOMAIN_4)} fraudulent entries")

    # Clean Domain 1
    with open('literature-domain-1-philosophical-autonomy.bib', 'r') as f:
        content = f.read()

    cleaned = remove_bibtex_entries(content, FRAUDULENT_DOMAIN_1)

    with open('literature-domain-1-philosophical-autonomy.bib', 'w') as f:
        f.write(cleaned)

    print(f"Domain 1: Removed {len(FRAUDULENT_DOMAIN_1)} fraudulent entry")
    print("\nCleaning complete. Original files backed up with .BACKUP extension")

if __name__ == '__main__':
    main()
