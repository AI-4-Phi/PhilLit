# `\uXXXX` escapes leak from search-result JSON into delivered bibliographies

**Status**: **FIXED 2026-08-11** (`dc606de`) — emitters no longer escape, and
the three tracked example reviews were repaired under the public-examples
exception. Left the roadmap the same day. See "Fix" below for what was
deliberately NOT done.
**Found** 2026-08-06, by the whole-branch review of item 3 D (venue vetting),
while measuring how many corpus `journal` values carry backslashes. Not a
venue-vetting bug — it predates item 3 D, venue vetting, and affects any
field an agent copies
out of a search result.

## The defect

No script in `skills/` or `hooks/` passes `ensure_ascii=False` to `json.dump` /
`json.dumps` — **zero occurrences repo-wide** (verified 2026-08-06). Python's
default is `ensure_ascii=True`, which escapes every non-ASCII character:

```python
>>> json.dumps({"journal": "Oñati Socio-legal Series"})
'{"journal": "O\\u00f1ati Socio-legal Series"}'
>>> json.dumps({"journal": "Oñati Socio-legal Series"}, ensure_ascii=False)
'{"journal": "Oñati Socio-legal Series"}'
```

That is correct, standards-conformant JSON, and a *parser* decodes it back to
`ñ` with no loss. The failure is that a research agent does not always parse it
— it reads the tool output as text and copies the venue name into a `.bib`
verbatim. The escape then survives into the delivered bibliography, where it is
neither valid BibTeX nor readable prose.

## Confirmed instances

| entry | field | value | where |
|---|---|---|---|
| `huq2024comparative` | `journal` | `Droit Public Comparé` | `reviews/administrative-power-legitimacy/`, `reviews/work-life-balance-ethics/` (both **untracked, local**) |
| `Tkachuk2024labor` | `journal` | `Przegląd Prawniczy...` | same two reviews |
| — | `abstract` | begins `{\u3cp\u3eRecently...` | `reviews/metaphilosophy-literature-reviews/literature-all.bib:2137` — **tracked, and it ships as a linked example** |

The third one matters most: it is in a review the README links, so it is
public. (`grep -c` finds 5 escape-bearing lines in that file.)

Note the `\u3c` case is a compounded failure — that is an HTML `<` that was
already escaped once as `&lt;`-style entity data, then JSON-escaped again, so
the abstract carries markup fragments as well as escapes.

## Why the cleaner does not catch it

`hooks/metadata_cleaner.py` only ever removes fields in `CLEANABLE_FIELDS`
(`journal`, `booktitle`, `volume`, `number`, `pages`, `publisher`, `doi`) and
only on a *source-authority* verdict. An escaped-but-otherwise-plausible venue
name is not a contradiction against CrossRef in any way the cleaner tests, and
`abstract` is not in the set at all.

## Fix — APPLIED 2026-08-11 (`dc606de`)

`ensure_ascii=False` at the agent-facing emitters, exactly the sites listed
here: `output.py` (the shared funnel for every search script), `verify_paper.py`
and `get_abstract.py`, each of which keeps its own emit path but now imports the
one decision instead of copying it.

Both cautions above were honoured, and both were real:

1. **`search_cache.py:54` was left alone.** It builds a cache *key* from sorted
   params; re-encoding it would silently invalidate every cached entry.
2. **Windows is handled, not assumed away.** Files were always safe (opened
   `encoding='utf-8'`), but stdout was not. `output.stdout_accepts_unicode()`
   puts stdout into UTF-8 and falls back to escapes when it cannot — so a
   cp1252 console gets a mangled name rather than a `UnicodeEncodeError` that
   kills the search. Both branches are pinned by
   `tests/test_json_unicode_output.py`.

The "separate, smaller question" — a normalization pass decoding existing
`\uXXXX` in bib fields — was **not** built, and should not be without new
evidence. It would have to run over delivered reviews, which the wrong-years
audit's standing rule forbids touching; the public examples were repaired
directly instead, which is the same exception that rule already carries.

**Corpus note:** 7 of the 43 local review bibs carried escapes at fix time.
Those are delivered reviews and stay as delivered. Only the tracked examples
were repaired (5 escapes across two of them, including
`author = {Medina, José}` and the `\u3c` markup case above), and
`tests/test_json_unicode_output.py` now fails if an escape reappears in any of
the three.
