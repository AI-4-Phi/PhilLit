"""
Philosophy research skill scripts package.

Scripts in this directory can be run as standalone CLI tools:
    python scripts/s2_search.py "free will" --limit 20

Or imported as modules:
    from scripts.output import output_success
    from scripts.s2_formatters import format_paper

This __init__.py enables proper imports without the sys.path.insert hack.
"""

# Re-export common utilities for convenient imports
from .rate_limiter import ExponentialBackoff, RateLimiter, get_limiter
from .search_cache import cache_key, get_cache, put_cache, clear_cache
from .output import output_success, output_partial, output_error, log_progress, make_error
from .s2_formatters import (
    format_paper,
    format_citation,
    S2_BASE_URL,
    S2_FIELDS,
    S2_PAPER_FIELDS,
    S2_CITATION_FIELDS,
    S2_RECOMMEND_FIELDS,
)
