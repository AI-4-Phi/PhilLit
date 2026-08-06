# `\uXXXX` escapes leak from search-result JSON into delivered bibliographies

**Found** 2026-08-06, by item 3 D's whole-branch review, while measuring how
many corpus `journal` values carry backslashes. Not a venue-vetting bug — it
predates item 3 D and affects any field an agent copies out of a search result.

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

## Fix (not applied — needs its own task)

Cheapest and most complete fix is upstream, at the point the search scripts
serialize: pass `ensure_ascii=False` in the `json.dump`/`json.dumps` calls that
produce **agent-facing** output, so the text an agent copies is already the
character it should write. Candidate sites (verified present 2026-08-06):
`skills/philosophy-research/scripts/output.py:65,85`,
`verify_paper.py:76,96`, `get_abstract.py:72,78`.

Two cautions for whoever takes it:

1. **Not every `json.dumps` should change.** `search_cache.py:54` builds a
   cache *key* from sorted params — changing its encoding silently invalidates
   every cached entry. Leave key-construction alone.
2. **Windows.** `CLAUDE.md` warns that non-ASCII in output piped through
   subprocesses can fail to encode under `cp1252`. Emitting real `ñ` instead of
   `ñ` moves non-ASCII into stdout that previously had none, so this needs
   an explicit encoding check on the Windows path, not just a flag flip.

A separate, smaller question: whether to also add a normalization pass that
decodes existing `\uXXXX` sequences in a bib field, which would repair the
three instances above rather than only preventing new ones.
