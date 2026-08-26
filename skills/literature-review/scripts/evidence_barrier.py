"""Transactional evidence barrier -- run once at the Phase 3->4 boundary.

Order: manifest validation -> SEP/IEP context acquisition -> report -> stamp.
Accuracy gate: fails CLOSED. run_barrier() mutates nothing -- it returns the
report plus every domain's final stamped content, built in memory; execute()
then atomically writes the report FIRST, then each bib. A crash before the
write phase leaves every file untouched; a crash mid-write leaves a prefix of
domains stamped with exit 1 (documented residual -- SKILL.md halts on
nonzero, and unstamped files read as all-EVIDENCE-NONE downstream).
Per-domain problems degrade (status: "degraded") and can only demote the
affected entries. All maps are per-domain: same-key entries in different
domains never share attestations.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import enrich_bibliography as eb
from enrich_bibliography import add_field_to_entry
import resolve_context as rc
import stamp_evidence as se
import web_evidence as wv
import year_suffix as ys

try:
    import venue_vetting as vv
except Exception:  # optional pass -- never block the accuracy gate
    vv = None


def _load_ledger(path: Path, expected_bib_name: str, kind: str):
    """(state, payload): present / missing / malformed. Never raises."""
    if not path.exists():
        return "missing", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return "malformed", None
    if not isinstance(data, dict):
        return "malformed", None
    # TYPE first, then membership. `in` compares with `==`, and JSON `true`
    # and `1.0` both equal the int 1 -- so a ledger whose version is a bool
    # or a float used to read as a valid version-1 ledger. `type(v) is int`,
    # NOT isinstance: bool subclasses int, so isinstance admits `true`.
    version = data.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        return "malformed", None
    if data.get("bib_file") != expected_bib_name:
        return "malformed", None  # stale/copied ledger -- reject
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return "malformed", None
    if kind == "cleaning":
        for v in entries.values():
            if not isinstance(v, dict) or v.get("verified_identifier") not in (
                    "doi", "publisher", None):
                return "malformed", None
    return "present", data


def _parseable_bib(path: Path) -> bool:
    from pybtex.database import parse_file
    from pybtex.scanner import PybtexError
    try:
        parse_file(str(path), bib_format="bibtex")
        return True
    except (PybtexError, OSError, UnicodeDecodeError):
        return False


def _keywords_has_evidence_web(keywords: str | None) -> bool:
    """True iff "evidence-web" appears as an EXACT comma-separated keyword
    token (casefolded), not merely as a substring -- a naive `in` check
    false-positives on a hypothetical keyword like
    "pre-EVIDENCE-WEB-candidate" (external review, 2026-08-17)."""
    return any(
        t.strip().casefold() == "evidence-web"
        for t in (keywords or "").split(",")
    )


_ABSTRACT_FIELD_RE = re.compile(r'\babstract\s*=', re.IGNORECASE)


def _heal_splice_is_well_formed(chunk: str) -> bool:
    """Defense-in-depth check run after a heal splice (review finding 1b):
    the splice must have produced EXACTLY ONE `abstract =` field, AND the
    resulting single-entry chunk must be pybtex-parseable.

    Neither check alone suffices. A duplicate field -- the exact review
    finding 1 shape, a stale nested-brace field the locator couldn't bound
    left behind alongside a newly INSERTED one -- is not guaranteed to
    raise in pybtex, so the count is the guaranteed catch for that case.
    Conversely a restored value that itself contains an unbalanced brace
    produces a single (correctly-counted) but unparseable field, which
    only the pybtex check catches. Fail-closed: any exception from pybtex
    counts as NOT well-formed. (Accepted residual: a restored abstract
    whose prose happens to literally contain the substring "abstract ="
    would trip the count and spuriously drop a good heal -- fail-closed is
    the right default here.)
    """
    if len(_ABSTRACT_FIELD_RE.findall(chunk)) != 1:
        return False
    from pybtex.database import parse_string
    try:
        parse_string(chunk, bib_format="bibtex")
    except Exception:
        return False
    return True


def _heal_abstract(fields: dict, ledger_entry: dict, debug: bool = False):
    """Restore an attested abstract after a post-attestation mutation.

    A/B root cause 2 (2026-07-25, domain 5): a researcher re-emitted its
    bib after enrichment and mutated 7 attested abstracts. Re-fetch by the
    entry's identifiers; the gate is HASH EQUALITY with the ledger value,
    so which API returns the text is irrelevant to integrity. Returns the
    restored text or None. Never raises (fail-closed: no heal, entry
    proceeds unattested exactly as before this feature). The resolver
    stub below assumes resolve_abstract_for_entry reads only
    entry['fields'] (true today) -- if it ever reads key/raw, resolution
    degrades to a failed heal, never a crash.
    """
    if not isinstance(ledger_entry, dict):
        return None
    target = ledger_entry.get("abstract_sha256")
    source = (ledger_entry.get("abstract_source") or "").strip().lower()
    if not target or not source:
        return None
    entry = {"key": "", "fields": fields, "raw": ""}
    try:
        if source == "ndpr":
            fetched, _ = eb.resolve_ndpr_abstract(
                fields.get("title", ""), eb.get_author_last_name(entry), debug)
        else:
            fetched, _ = eb.resolve_abstract_for_entry(
                entry,
                os.environ.get("S2_API_KEY", ""),
                os.environ.get("OPENALEX_EMAIL", ""),
                os.environ.get("CORE_API_KEY", ""),
                debug,
            )
    except Exception:
        return None
    if fetched and se.abstract_hash(fetched) == target:
        return fetched
    return None


# Three corroboration outcomes this file owns, on top of the four
# enrich_bibliography.corroborate_abstract returns. None is evidence: like
# every non-corroborated outcome they leave the entry unattested.
#
# PROBE_UNAVAILABLE: `compute_tier` could never grant this claim, or the
# CLAIMED source cannot be asked at all in THIS environment -- decided
# before any request. The tradeoff is real and worth stating in the
# direction it actually runs: the corroborator accepts ANY source's matching
# text, so a DOI-bearing candidate whose claimed source is unaskable could
# still have been corroborated by a fallback, and pre-classifying gives that
# up. What it buys is the meaning of `source_empty` -- "a source was probed
# and authoritatively has no abstract", the reading item 15's rate depends
# on -- which a fallback sweep launched from an unaskable claim would blur,
# since all three of corroborated / mismatch / source_empty are reachable
# that way. The give-up is small in honest runs: enrichment only writes
# `abstract_source = core` when a key was configured and `= s2` when a DOI
# resolved, so an unaskable claim means the environment or the entry changed
# after enrichment.
#
# PROBE_ERROR: an exception escaped the corroborator itself. Its probes are
# individually wrapped, but the shared client/limiter setup around them is
# not, and a plumbing failure there must not fail the whole barrier and
# take down the review -- same fail-closed-but-survivable treatment
# `_heal_abstract` gives its own fetch, for the same reason.
#
# CORROBORATION_DEADLINE: the pass ran out of budget or tripped its
# consecutive-error breaker before reaching this candidate, which was
# therefore never probed. PENDING, not disproven -- exactly like
# `transport_failed`: the barrier re-derives every attestation on every run,
# so a re-run restores the tier, and an outage can only lower tiers.
PROBE_UNAVAILABLE = "probe_unavailable"
PROBE_ERROR = "probe_error"
CORROBORATION_DEADLINE = "corroboration_deadline"

# The corroboration sweep's two bounds, mirroring venue_vetting's pair for
# the same reason it has them: this is the only unbounded network pass left
# inside a barrier that runs under SKILL.md's single 600 s Bash ceiling,
# whose documented failure mode is an orphaned barrier leaving every entry
# EVIDENCE-NONE. Its siblings are bounded at 600 s (resolve_context's
# article fetches) and 120 s (venue vetting); corroboration gets the
# smallest of the three because it is the one that scales with the number
# of ENTRIES rather than the number of articles or venues, and because
# every candidate it skips is restored on the next run.
#
# Both bounds are checked BEFORE a probe, so they bound the LOOP, not the
# pass: one in-flight `corroborate_abstract` call can still run past the
# deadline for as long as its own per-source timeouts and single retry
# allow (up to four sources). Worst-case wall time is therefore the
# deadline plus one full corroboration, not the deadline alone -- the same
# caveat venue_vetting states about REQUEST_TIMEOUT.
CORROBORATION_MAX_CONSECUTIVE_ERRORS = 3
CORROBORATION_PASS_DEADLINE_SECONDS = 180.0


class _CorroborationBudget:
    """Wall-clock deadline + consecutive-error breaker for one barrier run.

    The clock starts LAZILY, on the first probe this pass is actually asked
    to allow, rather than at construction. State the bound exactly, because
    it is narrower than it looks: corroboration and the heal fetches share
    one per-entry loop, so the lazy start shields only the work that PRECEDES
    the first probe (heals over earlier entries, the parse and ledger reads).
    Every heal after that point runs inside the window and does count against
    the 180 s, which can stop the pass on candidates a quiet run would have
    probed. That direction is fail-closed -- those candidates bucket
    `corroboration_deadline`, carry a lower tier, and are re-derived on the
    next run -- so it is accepted rather than fixed with a second clock.

    "Error" means a non-answer -- `transport_failed` or `probe_error`. A
    corroboration, a mismatch or an authoritative empty is an ANSWER: it
    tells the barrier something true about the entry, so it resets the
    streak exactly as a successful lookup does in venue_vetting. Both
    bounds are sticky: once the pass stops probing it stays stopped, so the
    outcome cannot flip back and forth entry by entry within one run.

    A SKIPPED candidate is neither, and deliberately does not touch the
    streak (the same thing venue_vetting says about cache hits): the free
    bound and the environment pre-classification return before `record` is
    ever called, because the streak counts consecutive non-answers from the
    network, not "candidates since the last network success". Resetting on a
    skip would let a run of unprobeable claims hide a live outage.

    An unrecognized token neither counts nor resets, for the same reason
    `_corroboration_summary` keeps an `other` bucket: the outcome set is not
    trusted to stay fixed, and a token this class has never seen is no
    evidence either way about the network.
    """

    def __init__(self, deadline_seconds=None, max_consecutive_errors=None):
        # Read the module constants at CONSTRUCTION, not import, so a test
        # (or a future caller) can monkeypatch them.
        self.deadline_seconds = (CORROBORATION_PASS_DEADLINE_SECONDS
                                 if deadline_seconds is None
                                 else deadline_seconds)
        self.max_consecutive_errors = (CORROBORATION_MAX_CONSECUTIVE_ERRORS
                                       if max_consecutive_errors is None
                                       else max_consecutive_errors)
        self._deadline = None
        self.consecutive_errors = 0
        self.stopped = False

    def allows_probe(self) -> bool:
        if self.stopped:
            return False
        if self._deadline is None:
            self._deadline = time.monotonic() + self.deadline_seconds
            return True
        if time.monotonic() >= self._deadline:
            self.stopped = True
            return False
        return True

    def record(self, outcome: str) -> None:
        if outcome in (eb.TRANSPORT_FAILED, PROBE_ERROR):
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.max_consecutive_errors:
                self.stopped = True
        elif outcome in (eb.CORROBORATED, eb.MISMATCH, eb.SOURCE_EMPTY):
            self.consecutive_errors = 0


def _heal_bucket(source: str, outcome: str) -> dict:
    """A heal-path corroboration bucket, in one place because it is written
    from three sites (restored, unhealed, and the output loop's correction
    when the splice is dropped) and they must not drift apart.

    `via: heal` marks the population: candidacy FAILED for these entries, so
    they are not part of the candidate rate item 15 reads -- their own
    fetch, hash-gated against the ledger, is what stands in for a probe.

    Both `source` and `claimed` carry the LEDGER's source, and neither is
    the resolver that answered: `_heal_abstract` discards that (integrity
    comes from the hash, not the messenger), so it is genuinely unrecorded
    rather than omitted here. `claimed` is the ledger's rather than the
    bib's for the same reason -- on an UNHEALED entry the bib's own
    `abstract_source` may say something else entirely, and it is the ledger
    record that this bucket is reporting on.
    """
    return {"outcome": outcome, "source": source, "claimed": source,
            "via": "heal"}


def _claimed_source_unprobeable(fields: dict, claimed: str) -> bool:
    """Can the claimed abstract source be asked about THIS entry, here?

    Every shape where the answer is a flat no, each read off
    `_probe_candidate`'s own preconditions rather than guessed at:

    * `core` with no API key -- resolution skips keyless CORE rather than
      burn futile unauthenticated attempts (item 13 D3), so the probe
      returns "empty" without a request. Tested with the RAW truthiness of
      the environment value, deliberately not stripped: `_probe_candidate`
      gates on `if not core_api_key`, so a whitespace-only key is probed
      there and must be probed here too. Parity with the probe is the whole
      point of this predicate -- a check that disagrees with it in either
      direction is a bug, and the disagreement this avoids would demote an
      entry the probe would have answered for.
    * `s2` or `openalex` with no DOI -- a bib entry carries no Semantic
      Scholar or OpenAlex id, so the DOI is the only identifier either
      probe has (`_probe_candidate` gates both on `if not doi`). Read
      through `eb.get_doi`, the same extractor the corroborator uses, for
      that same parity reason: mislabeling a PROBEABLE entry unprobeable
      would demote an honest attestation, the one error direction that
      costs a tier. Both need a field the entry's own enrichment must have
      had (both resolvers are DOI-gated), i.e. a later deletion.
    * `ndpr` with no title -- NDPR resolution is a title search over
      review essays; `_probe_candidate` gates on the stripped title, so
      the same expression is used here (parity again). NOT the same
      zero-network shape as s2/openalex whenever a DOI survives: those
      probes gate on DOI, so a title-less ndpr claim with a DOI would
      still reach a full corroboration's DOI-gated s2/openalex fallbacks
      (and a keyed core) and could be corroborated through one of them.
      Pre-classifying it here forecloses that fallback path -- accepted
      for the same reason as the s2/openalex foreclosure below: the
      contract is "can the CLAIMED source be asked", not "is there any
      answer at all". Zero-network only when the entry also lacks a DOI
      and a CORE key, and near-unreachable regardless, since a title-less
      entry is broken upstream.

    Pre-classification forecloses the fallback probes a full corroboration
    would still run for these claims (e.g. core-by-title for a DOI-less s2
    claim when a CORE key is set) -- accepted: this predicate's contract
    is "can the CLAIMED source be asked", and streak integrity (a
    zero-network SOURCE_EMPTY resets the consecutive-transport streak,
    hiding a live outage) outweighs a rare fallback corroboration.
    """
    if claimed == "core":
        return not os.environ.get("CORE_API_KEY", "")
    if claimed in ("s2", "openalex"):
        return not eb.get_doi({"fields": fields})
    if claimed == "ndpr":
        return not (fields.get("title") or "").strip()
    return False


def _corroborate_candidate(fields: dict, budget: "_CorroborationBudget",
                           debug: bool = False) -> dict:
    """One candidate's corroboration bucket, as the report records it.

    Ledger equality only makes an entry a CANDIDATE (item 15): the ledger
    is agent-written, so the three-line forgery -- fabricate an abstract,
    write `abstract_source`, write the fabricated text's own sha256 --
    satisfies it by construction. The tier needs a live fetch that still
    serves the same text.

    `source` is who ANSWERED (integrity-irrelevant: the gate is hash
    equality, so any source's matching text is equally good evidence),
    `claimed` is what the bib said. Both are recorded on every bucket
    because their DIFFERENCE is what makes the item-15 rate readable --
    a mismatch off a source the entry never claimed reads very differently
    from one off the source it did. On a NON-corroborated outcome nobody
    answered, so `source` falls back to `claimed`: on those buckets it
    records the claim, not an answerer (attribution imprecision only -- no
    outcome is decided by it).

    Three gates run BEFORE any request, in cost order. The free bound comes
    first: a claim outside `se.ATTESTED_ABSTRACT_SOURCES` can never reach
    TIER_ABSTRACT whatever a fetch says (compute_tier requires membership),
    so probing it spends a fetch on a decision already made. Then the
    environment pre-classification, then the pass budget -- so an entry
    skipped for a reason of its own is labelled with that reason rather
    than with the budget's.
    """
    claimed = (fields.get("abstract_source") or "").strip().lower()
    if (claimed not in se.ATTESTED_ABSTRACT_SOURCES
            or _claimed_source_unprobeable(fields, claimed)):
        return {"outcome": PROBE_UNAVAILABLE, "source": claimed,
                "claimed": claimed}
    if not budget.allows_probe():
        return {"outcome": CORROBORATION_DEADLINE, "source": claimed,
                "claimed": claimed}
    try:
        outcome, matched = eb.corroborate_abstract(
            fields,
            os.environ.get("S2_API_KEY", ""),
            os.environ.get("OPENALEX_EMAIL", ""),
            os.environ.get("CORE_API_KEY", ""),
            debug,
        )
    except Exception:
        budget.record(PROBE_ERROR)
        return {"outcome": PROBE_ERROR, "source": claimed, "claimed": claimed}
    budget.record(outcome)
    return {"outcome": outcome, "source": matched or claimed,
            "claimed": claimed}


def _corroboration_summary(report: dict) -> dict:
    """Operator-facing counts over the corroboration buckets.

    Heal-path buckets (`via: heal`) are excluded: they are a different
    population (candidacy FAILED there) already summarized by
    `report["healed"]`, and folding them in would inflate the corroborated
    count that item 15's rate reads. `candidates` is the sum of the rest by
    construction, and `other` exists so a token added later cannot go
    silently uncounted -- the key set is fixed either way, since a consumer
    must not have to guess which keys a given run will print.
    """
    counts = {k: 0 for k in (eb.CORROBORATED, eb.MISMATCH, eb.SOURCE_EMPTY,
                             eb.TRANSPORT_FAILED, PROBE_UNAVAILABLE,
                             PROBE_ERROR, CORROBORATION_DEADLINE)}
    counts["other"] = 0
    total = 0
    for per_bib in (report.get("abstract_corroboration") or {}).values():
        for bucket in (per_bib or {}).values():
            if not isinstance(bucket, dict) or bucket.get("via") == "heal":
                continue
            total += 1
            outcome = bucket.get("outcome")
            counts["other" if outcome not in counts else outcome] += 1
    return {"candidates": total, **counts}


_DERIVED_FIELD_RE = re.compile(
    r"\n[ \t]*(?:venue_status|year_suffix|urldate|archiveurl)\s*=\s*"
    r"(?:\{[^{}]*\}|\"[^\"]*\")\s*,?",
    re.IGNORECASE)


def _strip_derived_fields(entry_text: str) -> str:
    """Remove every pre-existing derived field it can find.

    The barrier OWNS all four (item 3 D's venue_status, item 3 F's
    year_suffix, item 2's urldate and archiveurl): each is re-derived from
    scratch on every run -- venue_status from OpenAlex, year_suffix from the
    current union of every domain bibliography, urldate from the capture's
    retrieved_at and archiveurl from the archive lookup -- so a value already
    in the file is either stale or
    hand-written, and both must go before this run decides. Without this, a
    flag or letter survives a later run that had no API key, or whose domain
    set changed -- a false discredit or a wrong letter that no later pass can
    clear.

    THREE documented limits, accepted rather than fixed. Two are about the
    field's VALUE (single-nesting-level shape, same reasoning as
    resolve_context.strip_context_fields); the third is orthogonal and about
    its POSITION. All three apply identically to both fields.

    1. VALUE, bare token: `venue_status = low-visibility,` is NOT stripped --
       the pattern requires a braced or quoted value.
    2. VALUE, nested braces: `venue_status = {low {x} vis}` is NOT stripped --
       the braced alternative is `\\{[^{}]*\\}`, one nesting level only.
    3. POSITION, not line-initial: the pattern is anchored to `\\n[ \\t]*`, so
       it only matches a field that OPENS its line. An occurrence sharing a
       line with anything else survives -- verified through the real
       execute(): `@article{k, venue_status = {low-visibility},` on the
       header line, `author = {A}, venue_status = {low-visibility},`
       mid-entry, and `year = {2020}, venue_status = {low-visibility}`
       trailing, all three kept the field.

    Deliberately NOT fixed by widening the anchor. This pattern has no
    brace-nesting awareness at all, so any start alternative looser than
    `\\n` (e.g. `[\\n,]`) can begin a match INSIDE a braced value -- an
    abstract or note containing `, venue_status = {...}` would be silently
    truncated. Trading a cosmetic miss for value corruption in a fail-closed
    accuracy gate is the wrong trade; closing it properly means a real field
    parser, which is a rewrite, not a fix.

    What the limits do and do not cost: none of these shapes is ever produced
    by this barrier (add_field_to_entry always inserts the field on its own
    line), by pybtex's writer, or by dedupe_bib's text scanner, so reaching
    any of them takes a hand edit or an agent writing a compact multi-field
    line. Even then the barrier's own decision this run governs what is
    re-added: a run that DOES flag the entry overwrites the surviving value
    in place (add_field_to_entry's head_pattern matches on any leading
    whitespace), so only an UNFLAGGED run leaves a forged or stale value
    standing, and no duplicate-field corruption results either way.
    """
    return _DERIVED_FIELD_RE.sub("", entry_text)


# What the barrier writes OVER a `year_suffix` value it did not derive and
# `_strip_derived_fields` could not reach. Deliberately NON-EMPTY: both merge
# policies that carry the field through Phase 6 (dedupe_bib.merge_entries and
# generate_bibliography._carry_year_suffix) read an empty value as "winner
# missing" and COPY A LOSER'S LETTER BACK UP into it, which would silently
# undo the neutralisation in files this barrier no longer controls. A
# non-empty token lands in their "both non-empty and unequal" branch instead:
# the winner's value is preserved and the disagreement is announced. Every
# downstream reader of the field requires a single ASCII a-z letter
# (generate_bibliography._entry_suffix, check_evidence's same guard), so this
# reads as "no letter" to all of them while staying self-documenting in a
# delivered .bib.
SUFFIX_UNTRUSTED = "unassigned"

_SUFFIX_FIELD_RE = re.compile(r"\byear_suffix\s*=", re.IGNORECASE)


_VENUE_FIELD_RE = re.compile(r"\bvenue_status\s*=", re.IGNORECASE)

# The web gate's two derived fields take the same splice verification as
# venue_status/year_suffix (2026-08-16, from the service's whole-branch
# review of the item-2 intake): _strip_derived_fields only reaches a field
# that OPENS its line, so a compact hand-written urldate/archiveurl survives
# the strip and the very next splice inserts a DUPLICATE field pybtex
# rejects — losing an access date is survivable; an unparseable bib is not.
_URLDATE_FIELD_RE = re.compile(r"\burldate\s*=", re.IGNORECASE)
_ARCHIVEURL_FIELD_RE = re.compile(r"\barchiveurl\s*=", re.IGNORECASE)


def _derived_field_took(chunk: str, pre_splice: str, field: str, intended: str,
                        field_re: re.Pattern) -> bool:
    """Did a derived-field splice actually land, and is the result still a bib
    the real parser accepts? The shared core behind both derived fields.

    Three conditions, and each has its own failure it exists to catch:

    1. **The text changed.** `_stamp_optional_field` swallows any exception
       from `add_field_to_entry` and returns the text UNCHANGED -- deliberately,
       so an optional pass can never fail the barrier. But an unchanged chunk
       still parses and still holds exactly one field, so the other two checks
       alone say True and the caller reports a stamp that is not on disk.
    2. **The field now carries THIS run's value**, by a field PARSE rather than
       a substring test -- an abstract containing the literal text
       `venue_status = {low-visibility}` must not be mistaken for the field.
    3. **Exactly one instance, and pybtex accepts the chunk.**
       `add_field_to_entry` locates an existing field by `(\\s+)<field>\\s*=`,
       so a value written with NO whitespace before it
       (`@article{k,venue_status={x},`) is not found and the "add" path inserts
       a SECOND one -- and pybtex raises `DuplicateField` on that, which would
       hand dedupe_bib an unparseable bibliography and take down all of Phase
       6. Losing a flag is survivable; emitting a bib the real parser rejects
       is not.

    Condition 3 is why this matters for `venue_status` and not only for
    `year_suffix`: `_strip_derived_fields` only reaches a field that OPENS its
    line, so a compact pre-existing `venue_status` survives the strip and a
    duplicate becomes possible on the very next splice.
    """
    if chunk is pre_splice:
        return False
    if se.parse_entry_fields(chunk).get(field) != intended:
        return False
    if len(field_re.findall(chunk)) != 1:
        return False
    from pybtex.database import parse_string
    try:
        parse_string(chunk, bib_format="bibtex")
    except Exception:
        return False
    return True


def _splice_took(chunk: str, pre_splice: str, intended: str) -> bool:
    """Did the splice actually replace the stale value, AND stay well-formed?

    Both halves are required, and the first was missing until an external
    review found it (2026-08-06, kimi-k3 I1 / gpt-5.6-sol C3).
    `_stamp_optional_field` swallows any exception from `add_field_to_entry`
    and returns the text UNCHANGED -- deliberately, so an optional pass can
    never fail the barrier. But an unchanged chunk still holds exactly one
    `year_suffix =` and still parses, so the well-formedness check alone says
    True and the caller reports the entry as `residual_neutralized`. Nothing
    was neutralized: the stale letter survives into the delivered bib while
    the report claims it was cleaned.

    That is the "never silently" policy violated on the error path, and it is
    a live drop hazard downstream -- two surviving stale letters read as a
    structurally complete group in Phase 6, so `fully_lettered` is true and a
    prose `Johnson (2024a)` drops the other work, with the barrier having
    reported the hazard as fixed.

    So: confirm the field now actually carries the value this run intended,
    by a FIELD PARSE rather than a substring test (the same reason detection
    upstream parses rather than scans -- an abstract containing the literal
    text `year_suffix = {a}` must not be mistaken for the field).

    Only ever called when a residual was detected, i.e. only when a duplicate
    is possible: with no pre-existing field the splice always inserts exactly
    one, so an unconditional pybtex parse per lettered entry would buy nothing.
    """
    return _derived_field_took(chunk, pre_splice, "year_suffix", intended,
                               _SUFFIX_FIELD_RE)


def _venue_splice_took(chunk: str, pre_splice: str, status: str) -> bool:
    """The same question for `venue_status`, which had no answer at all until
    2026-08-11.

    The `year_suffix` half of this bug was fixed on 2026-08-06 (`78dd470`);
    this half was recorded and left open. It is the milder of the two -- a lost
    `venue_status` costs a caveat rather than dropping a cited work -- but it
    was a SILENT loss, which the gate-failure policy forbids in either
    direction, and condition 3 of `_derived_field_took` makes a duplicate
    field reachable here too.
    """
    return _derived_field_took(chunk, pre_splice, vv.VENUE_STATUS_FIELD, status,
                               _VENUE_FIELD_RE)


def _stamp_optional_field(entry_text: str, field: str, value: str) -> str:
    """Add an OPTIONAL engine-derived field, or return the text unchanged.

    Optional passes (item 3 D's venue_status) must not be able to fail the
    barrier, and that has to include their own splice, not just their network
    calls -- a regression here would otherwise turn a reviewable run into
    status "failed". Losing the field costs a caveat; losing the run costs the
    review.
    """
    try:
        return add_field_to_entry(entry_text, field, value)
    except Exception:
        return entry_text


def _att_blob(att: se.EntryAttestation, enrich_entry, context_value,
              web_url: str | None = None):
    """The attestation as the report records it -- and therefore as
    dedupe_bib.py rebuilds it when it re-stamps merged entries.

    `web_url` is the VALUE BINDING for the web gate, and it is why the flag
    cannot be persisted as a bare boolean: dedupe's rule is that one
    contributor's boolean must never authorize another contributor's field
    value, so the re-stamp has to be able to confirm the merged entry still
    carries the same URL this gate passed for.
    """
    return {
        "abstract_attested": att.abstract_attested,
        "abstract_source": (enrich_entry or {}).get("abstract_source"),
        "abstract_sha256": (enrich_entry or {}).get("abstract_sha256"),
        "context_written": att.context_written,
        "context_field": None if context_value is None else context_value[0],
        "context_sha256": None if context_value is None else se.abstract_hash(context_value[1]),
        "api_matched": att.api_matched,
        "verified_identifier": att.verified_identifier,
        "verified_identifier_value": att.verified_identifier_value,
        "breaker_tripped": att.breaker_tripped,
        "cleaning_abstained": att.cleaning_abstained,
        "web_gate_passed": att.web_gate_passed,
        "web_url": web_url,
    }


def run_barrier(review_dir: Path, n_domains: int, debug: bool = False):
    """Pure planning pass: returns (report, outputs) with NO file mutation.

    outputs: {bib_path: final_stamped_content} -- only parseable, present
    domains appear in it.
    """
    ijson = review_dir / "intermediate_files" / "json"
    report = {
        # 2 (was 1): the abstract attestation in this report is
        # corroboration-gated (item 15). Phase 6's re-stamp keys on this
        # version -- a version-1 report predates the gate, so its
        # `abstract_attested` flags carry only ledger-equality vintage and
        # must not be trusted to re-grant EVIDENCE-ABSTRACT there.
        "schema_version": 2, "status": "complete", "domains": {},
        "articles": {"fetched": [], "failed": []}, "acquisition": {},
        "attestations": {}, "stamps": {},
        "demoted_would_be_existence_v4": [],
        # Option C: entries whose cleaner abstention attests existence -- the
        # refusal must stay visible however the tier lands (§9, the retained
        # half of Option D).
        "cleaning_abstained": [],
        "healed": {},
        # Item 15: one bucket per CANDIDATE (ledger equality held) plus one
        # per heal, recording what a live fetch said. Every entry that
        # reaches EVIDENCE-ABSTRACT has a `corroborated` bucket here; every
        # other outcome is a visible, re-derivable demotion.
        "abstract_corroboration": {},
    }
    degraded = False
    domains = {}
    slug_paths = []
    for i in range(1, n_domains + 1):
        bib_name = f"literature-domain-{i}.bib"
        bib = review_dir / bib_name
        c_state, c_data = _load_ledger(
            ijson / f"cleaning_ledger-literature-domain-{i}.json", bib_name, "cleaning")
        e_state, e_data = _load_ledger(
            ijson / f"enrichment_ledger-literature-domain-{i}.json", bib_name, "enrichment")
        slug_paths.append(ijson / f"encyclopedia_entries-domain-{i}.json")
        if not bib.exists():
            b_state = "missing"
        elif not _parseable_bib(bib):
            b_state = "malformed"  # excluded from outputs -- never corrupt it
        else:
            b_state = "present"
        report["domains"][str(i)] = {
            "bib": b_state, "cleaning_ledger": c_state, "enrichment_ledger": e_state,
        }
        if b_state != "present" or c_state != "present" or e_state != "present":
            degraded = True
        if b_state == "present":
            domains[i] = {"bib": bib, "bib_name": bib_name,
                          "cleaning": c_data, "enrichment": e_data}

    slug_states, slug_union = rc.load_slug_files(slug_paths)
    for i in range(1, n_domains + 1):
        s = slug_states[str(slug_paths[i - 1])]
        report["domains"][str(i)]["slug_file"] = s
        if s in ("missing", "malformed"):
            degraded = True

    if not domains:
        report["status"] = "failed"
        return report, {}

    articles, failed = rc.fetch_articles(slug_union, debug=debug)
    report["articles"]["fetched"] = sorted(articles)
    report["articles"]["failed"] = failed
    if failed:
        degraded = True

    # Per-domain parse + attestations (KEYED PER DOMAIN -- never bare keys).
    parsed = {}        # i -> list[chunk]
    atts = {}          # i -> {key: EntryAttestation}
    needs_context = {} # "bib_name::key" -> {"entry_type", "fields"}
    healed = {}         # (i, key) -> (restored_text, canonical_source)
    # (i, key) of every entry a live fetch corroborated this run -- either
    # directly or via a heal. The output loop below re-derives ledger
    # equality per chunk (fail-closed against a splice that did not land)
    # and conjoins THIS set, so no path can attest an abstract that no fetch
    # backed.
    corroborated = set()
    # One budget per RUN, shared across domains: the bound exists to keep
    # the whole barrier inside SKILL.md's Bash ceiling, and a per-domain
    # budget would multiply by the domain count and bound nothing.
    corroboration_budget = _CorroborationBudget()
    for i, d in domains.items():
        chunks = [rc.strip_context_fields(_strip_derived_fields(c))
                  if se.entry_header(c) else c
                  for c in se.split_entries(d["bib"].read_text(encoding="utf-8"))]
        parsed[i] = chunks
        atts[i] = {}
        c_entries = (d["cleaning"] or {}).get("entries", {})
        breaker = bool((d["cleaning"] or {}).get("breaker_tripped"))
        e_entries = {
            k: v
            for k, v in ((d["enrichment"] or {}).get("entries", {}) or {}).items()
            if isinstance(v, dict)
        }
        report["acquisition"].setdefault(d["bib_name"], {})
        for chunk in chunks:
            header = se.entry_header(chunk)
            if not header:
                continue
            etype, key = header
            fields = se.parse_entry_fields(chunk)
            cl = c_entries.get(key) or {}
            att = se.EntryAttestation(
                api_matched=bool(cl.get("api_matched")),
                verified_identifier=cl.get("verified_identifier"),
                verified_identifier_value=cl.get("verified_identifier_value"),
                breaker_tripped=breaker,
                cleaning_abstained=cl.get("cleaning_abstained"),
            )
            e_rec = e_entries.get(key)
            # Ledger equality is CANDIDACY, not attestation (item 15).
            candidate = se.attest_abstract(fields, e_rec)
            if candidate:
                bucket = _corroborate_candidate(
                    fields, corroboration_budget, debug=debug)
                report["abstract_corroboration"].setdefault(
                    d["bib_name"], {})[key] = bucket
                if bucket["outcome"] == eb.CORROBORATED:
                    att.abstract_attested = True
                    corroborated.add((i, key))
            elif e_rec and e_rec.get("abstract_sha256"):
                # Keyed on CANDIDACY, exactly as before -- NOT on the
                # post-corroboration flag. A candidate that fails
                # corroboration could never be healed anyway: candidacy
                # already equated the bib's abstract hash with the ledger's,
                # so the heal's own gate (fetched hash == LEDGER hash) is the
                # very comparison corroboration just failed. Entering the
                # heal path there would only spend a redundant fetch: a
                # hash match there would itself be live corroboration, not
                # an attestation the gate had refused sneaking through, so
                # the only real cost is re-deriving the same no.
                restored = _heal_abstract(fields, e_rec, debug=debug)
                src = ((e_rec.get("abstract_source") or "").strip().lower())
                if restored is not None:
                    # The FIELD must carry the ledger's source -- that is
                    # what attest_abstract compares against. Which resolver
                    # actually served the text is integrity-irrelevant
                    # (hash-gated) and is not recorded in the bib.
                    att.abstract_attested = True
                    corroborated.add((i, key))
                    healed[(i, key)] = (restored, src)
                    report["healed"].setdefault(d["bib_name"], {})[key] = {
                        "outcome": "restored", "source": src}
                    # A heal IS a corroboration, by construction: the fetched
                    # text had to hash-equal the ledger value, and that text
                    # is what gets written into the bib. No second fetch.
                    report["abstract_corroboration"].setdefault(
                        d["bib_name"], {})[key] = _heal_bucket(
                            src, eb.CORROBORATED)
                else:
                    report["healed"].setdefault(d["bib_name"], {})[key] = {
                        "outcome": "unhealed", "source": src}
                    report["abstract_corroboration"].setdefault(
                        d["bib_name"], {})[key] = _heal_bucket(
                            src, "unhealed")
            atts[i][key] = att
            if att.abstract_attested:
                report["acquisition"][d["bib_name"]][key] = {"outcome": "not-needed"}
            else:
                needs_context[f"{d['bib_name']}::{key}"] = {
                    "entry_type": etype, "fields": fields}

    acq = rc.acquire_context(needs_context, articles)
    context_values = {}  # (i, key) -> (field, value)
    by_name = {d["bib_name"]: i for i, d in domains.items()}
    for qual_key, res in acq.items():
        bib_name, key = qual_key.split("::", 1)
        i = by_name[bib_name]
        report["acquisition"][bib_name][key] = {
            k: v for k, v in res.items() if k != "value"}
        if res["outcome"] == "matched":
            atts[i][key].context_written = True
            context_values[(i, key)] = (res["field"], res["value"])

    # Item 3 D: venue vetting. A PLUMBING pass inside a fail-closed gate --
    # it must never turn a reviewable run into a failed one, so everything is
    # wrapped and every failure means "no flags".
    venue_flags = {}   # (i, key) -> status token
    try:
        if vv is None:
            raise RuntimeError("venue_vetting unavailable")
        venue_names = {}   # (i, key) -> raw journal name
        for i, d in domains.items():
            for chunk in parsed[i]:
                header = se.entry_header(chunk)
                if not header:
                    continue
                journal = (se.parse_entry_fields(chunk).get("journal") or "").strip()
                if journal:
                    venue_names[(i, header[1])] = journal
        venue_report = vv.vet_venues(sorted(set(venue_names.values())))
        for ik, journal in venue_names.items():
            if venue_report["verdicts"].get(vv.normalize_venue_name(journal)):
                venue_flags[ik] = vv.STATUS_LOW_VISIBILITY
        # Inside the try, not after it: if venue_names is empty (no journal
        # field anywhere), the loop above never touches venue_report, so a
        # malformed (non-dict) return would otherwise reach an unguarded
        # subscript below and fail the whole barrier (self-review finding,
        # item 3 D). Keeping this assignment inside the safety boundary
        # means ANY exception here -- however it arises -- lands in the
        # except clause below instead.
        # Named "flagged_entries", not "stamped": this counts entries the
        # RULE decided to flag, not fields actually spliced into a bib --
        # _stamp_optional_field can still swallow an individual splice
        # failure below, and this count must not claim a stamp that does
        # not exist on disk. Since 2026-08-11 the stamps ARE counted too, in
        # `stamped_entries`, with failures named in `splice_failed`: honest
        # about not being a stamp count was never the same as reporting the
        # gap, and a silent loss is what the gate policy forbids.
        # Not bare "flagged": vet_venues's own return
        # already uses that key for its LIST of flagged venue names (see
        # venue_vetting.py's `result["flagged"]`) -- reusing it here would
        # silently overwrite that list with this int. "flagged_entries"
        # also matches the name execute() already prints in its summary.
        venue_report["flagged_entries"] = len(venue_flags)
        # report gets json.dumps'd whole in execute(), gated only on
        # OSError there -- a non-serializable value anywhere in vet_venues's
        # return (a stray object, NaN survives dict shape checks but a
        # custom type would not) would otherwise escape execute() as an
        # uncaught TypeError: no stdout summary, no report written, and the
        # bibs never written either, since they are gated on the report
        # write succeeding. Round-tripping here, still inside the try,
        # demotes that all the way down to the already-tested "error" path.
        venue_report = json.loads(json.dumps(venue_report))
    except Exception as exc:
        venue_flags = {}
        venue_report = {"status": "error", "error": repr(exc), "flagged_entries": 0}
    report["venue_vetting"] = venue_report

    # Item 2: web-source evidence. A PLUMBING pass inside a fail-closed gate,
    # wrapped like venue vetting -- but with TWO boundaries, and the difference
    # is load-bearing. The OUTER try is for pass-level catastrophes (the JSON
    # round-trip below). The INNER one, per entry, is for DATA problems: without
    # it, one malformed URL would revoke promotion from every other web entry in
    # the review, and the spec requires entry-level failures to degrade to
    # no-promotion (external review, Q7.1).
    #
    # Promote-only by construction: every path either sets a gate flag or
    # leaves the entry exactly where it already was, and each non-promotion
    # lands in a NAMED bucket rather than nowhere.
    web_gates = {}    # (i, key) -> {"urldate": str, "archiveurl": str | None}
    web_report = {"status": "complete",
                  "gate_passed": {"script": 0, "agent": 0},
                  "no_capture": [], "no_existence": [],
                  "fetch_error": [], "capture_rejected": {},
                  "no_url": [], "entry_error": [],
                  "excluded_host": [],
                  # Diagnostic overlay, not an outcome bucket: entries listed
                  # here ALSO land in excluded_host. Means a PRIOR pass had
                  # promoted them (the exclusion shipped after v0.4.1
                  # populations did) -- same overlay pattern as wayback_failed.
                  "excluded_host_demoted": [],
                  # Diagnostic overlay, not an outcome bucket: entries listed
                  # here ALSO land in their outcome. Distinguishes "the
                  # availability API failed/throttled" from "no snapshot
                  # exists" (live acceptance, 2026-08-15).
                  "wayback_failed": [],
                  # Scope bucket, not an outcome: an abstract-bearing @misc is
                  # owned by the abstract attestation channel and may promote
                  # THERE, so it is deliberately absent from the summary's
                  # not_promoted count -- but it must land somewhere, or the
                  # every-non-promotion-lands-in-a-named-bucket claim above is
                  # false for this class (decided 2026-08-18).
                  "misc_with_abstract": []}
    try:
        for i, d in domains.items():
            for chunk in parsed[i]:
                header = se.entry_header(chunk)
                if not header:
                    continue
                etype, key = header
                fields = se.parse_entry_fields(chunk)
                # Scope: @misc only -- a url on an @article is decoration
                # (spec, Out of scope). The abstract narrowing below is a
                # deliberate DEPARTURE from the spec (whose scope rule is "a
                # @misc entry carrying a URL", with no abstract condition),
                # decided on its merits 2026-08-18: an abstract-bearing entry
                # already has its own attestation channel.
                if etype.lower() != "misc":
                    continue
                if fields.get("abstract"):
                    web_report["misc_with_abstract"].append(
                        f"{d['bib_name']}:{key}")
                    continue
                qual = f"{d['bib_name']}:{key}"
                try:
                    url = wv.extract_url(fields)
                    if not url:
                        web_report["no_url"].append(qual)
                        continue
                    ex_host = wv.excluded_host(url)
                    if ex_host:
                        # Scope, not failure: encyclopedia/index hosts never
                        # earn EVIDENCE-WEB (web_evidence owns the list), so
                        # no capture is read and no network probe runs --
                        # placed HERE so the existence probe cannot GET a
                        # crawl-delayed host even when an agent hand-wrote a
                        # capture for it.
                        web_report["excluded_host"].append(qual)
                        # A prior pass may have promoted this entry (the
                        # exclusion shipped after v0.4.1 populations did):
                        # signal the demotion so a re-run is auditable.
                        if _keywords_has_evidence_web(fields.get("keywords")):
                            web_report["excluded_host_demoted"].append(qual)
                        continue
                    # Capture FIRST, before any network. Two reasons, and the
                    # second is why this departs from the spec's ordering:
                    #   1. An entry with no capture cannot pass the gate, so
                    #      probing its URL buys nothing -- and the spec's stated
                    #      motive for looking anyway (delivery wants the
                    #      snapshot) does not apply, since archiveurl is only
                    #      spliced onto entries that DO pass.
                    #   2. It keeps the barrier network-free for reviews with no
                    #      captures at all, which is every pre-item-2 workspace
                    #      and every test that drives the real execute().
                    # The bucket is therefore `no_capture`, not the spec's
                    # `exists_no_capture`: with this order we have not checked
                    # existence, and claiming it would be a lie.
                    capture = wv.load_capture(review_dir, key)
                    if capture is None:
                        web_report["no_capture"].append(qual)
                        continue
                    # The capture's own URLs can betray a redirect onto an
                    # excluded host even when the bib URL is allowed -- a
                    # redirector must not smuggle SEP content past the
                    # exclusion, and the probe below must not run for it.
                    cap_host = (wv.excluded_host(capture.get("url") or "")
                                or wv.excluded_host(capture.get("final_url") or ""))
                    if cap_host:
                        web_report["excluded_host"].append(qual)
                        if _keywords_has_evidence_web(fields.get("keywords")):
                            web_report["excluded_host_demoted"].append(qual)
                        continue
                    ex = wv.evaluate_existence(url)
                    if ex.get("wayback_error"):
                        web_report["wayback_failed"].append(qual)
                    if not ex["exists"]:
                        web_report["no_existence"].append(qual)
                        continue
                    passed, reason = wv.check_capture(
                        capture, url, fields.get("title") or "",
                        fields.get("web_span") or "")
                    if reason == "fetch_error":
                        # The tool ran and failed: a reachability problem, not
                        # a compliance one. Kept apart on purpose.
                        web_report["fetch_error"].append(qual)
                        continue
                    if not passed:
                        web_report["capture_rejected"].setdefault(
                            reason, []).append(qual)
                        continue
                    prov = capture.get("provenance") or "script"
                    web_report["gate_passed"][prov] = \
                        web_report["gate_passed"].get(prov, 0) + 1
                    web_gates[(i, key)] = {
                        "urldate": (capture.get("retrieved_at") or "")[:10],
                        "archiveurl": ex["archiveurl"],
                    }
                except Exception as exc:
                    web_report["entry_error"].append(f"{qual}: {exc!r}")
                    continue
        # Round-tripped inside the try for the same reason venue vetting is: a
        # non-serializable value would otherwise escape execute() as an
        # uncaught TypeError, and the bibs are gated on the report write.
        web_report = json.loads(json.dumps(web_report))
    except Exception as exc:
        web_gates = {}
        web_report = {"status": "error", "error": repr(exc),
                      "gate_passed": {"script": 0, "agent": 0},
                      "no_capture": [], "no_existence": [],
                      "fetch_error": [], "capture_rejected": {},
                      "no_url": [], "entry_error": [],
                      "excluded_host": [], "excluded_host_demoted": [],
                      "wayback_failed": [], "misc_with_abstract": []}
    report["web_sources"] = web_report

    # Item 3 F: a `year_suffix` that survived _strip_derived_fields. The
    # stripper only matches a field OPENING its line, an accepted limit
    # documented there and adjudicated for `venue_status` as "document, don't
    # widen" -- a stale FLAG is a metadata problem. For `year_suffix` it is a
    # correctness one, because the value is ACTED ON: if every member of a
    # Phase 6 collision group happens to retain a distinct stale letter,
    # generate_bibliography's `fully_lettered` gate becomes true on values
    # this barrier never derived, and a cited work is dropped. Measured on
    # the real execute(): two DIFFERENT people sharing a surname and a year
    # (the case F deliberately refuses to letter) keep compact stale `a` and
    # `b` all the way into the output bib.
    #
    # Detection is by se.parse_entry_fields -- a FIELD parse, not a substring
    # scan. That is the whole reason detecting is safe where stripping is
    # not: the stripper's veto is that a looser text anchor can begin a match
    # INSIDE a braced value and truncate an abstract, and a field parse
    # cannot (verified: an abstract containing the literal text
    # `year_suffix = {a}` is not detected). Not claimed to be complete --
    # a value the parser mis-bounds may slip past, which is harmless, since
    # nothing that is not a single a-z letter reads as a letter downstream.
    #
    # OUTSIDE the assignment try/except below, deliberately: nested inside
    # it, an assignment exception would hide the residual -- precisely the
    # silence this detection exists to end.
    residual_suffix = set()   # (i, key) with an untrusted value on entry
    for i, d in domains.items():
        for chunk in parsed[i]:
            header = se.entry_header(chunk)
            if not header:
                continue
            if (se.parse_entry_fields(chunk).get("year_suffix") or "").strip():
                residual_suffix.add((i, header[1]))

    # Item 3 F: Chicago a/b letters, assigned ONCE over the union of every
    # domain so the same work carries the same letter in every copy. Pure
    # computation, but wrapped like the venue pass: a failure here must cost
    # the letters this run would have ASSIGNED, never the run.
    #
    # Note what that does NOT say. A failure here cannot cost a letter
    # ALREADY IN THE FILE that the stripper could not reach -- an earlier
    # version of this comment claimed assignment failure "must cost letters"
    # flatly, which is false in exactly that case. Those are handled by the
    # residual pass above and the neutralisation below, both of which run on
    # the error path too (`suffix_map` is empty there, so every residual
    # entry is neutralised rather than overwritten with a fresh letter).
    suffix_map = {}   # (i, key) -> letter
    try:
        suffix_inputs = []
        for i, d in domains.items():
            for chunk in parsed[i]:
                header = se.entry_header(chunk)
                if not header:
                    continue
                fields = se.parse_entry_fields(chunk)
                suffix_inputs.append({
                    "id": (i, header[1]),
                    "author": fields.get("author", ""),
                    "editor": fields.get("editor", ""),
                    "year": fields.get("year", ""),
                    "title": fields.get("title", ""),
                    "doi": fields.get("doi", ""),
                })
        assignment = ys.assign_suffixes(suffix_inputs)
        suffix_map = assignment["suffixes"]
        # groups/overflow/suppressed/conflicts are ALREADY plain, JSON-serializable
        # structures (lists of dicts / lists of repr() strings) -- pass them
        # through unchanged. An earlier revision wrapped overflow in
        # `[list(x) for x in ...]`, which on a list of DICTS returns each
        # dict's KEY NAMES ("authors", "year", "works") instead of its
        # values, discarding exactly the information a human needs to act on
        # an overflow group ("this a/b run is >26 same-author-same-year
        # works and got no letters at all -- who, what year, how many"). The
        # whole point of the >26 rule is that this must be reported, not
        # silent (year_suffix.py's own docstring for the coherence check
        # says the same of `conflicts`), so all four reach the report
        # as-is.
        #
        # `suppressed` is the same class of report as `overflow`: a group the
        # assigner deliberately left unlettered -- because a conflicting-DOI
        # pair, an identity conflict, or a copy the usability filter dropped
        # would otherwise letter it only in part. Whole-group suppression is
        # the right call (a half-lettered group breaks the module's own
        # invariant and would let generate_bibliography drop a cited work),
        # but it is invisible to an operator unless it is reported: the bib
        # simply comes back with no letters and nothing says why.
        # `suppressed` and `suppressed_singletons` are one partition, not a
        # list and a filtered view of it: a suppressed group whose work count
        # is 1 could never have been lettered anyway (Chicago disambiguation
        # starts at two works), so reporting it alongside the real ones buried
        # 8 actionable records under 98 non-actionable ones on the real corpus.
        # Both are carried, because "nothing the assigner declined is
        # invisible" is the point of these keys -- a consumer that wants
        # everything unions them.
        suffix_report = {"status": "complete", "assigned": len(suffix_map),
                         "groups": assignment["groups"],
                         "overflow": assignment["overflow"],
                         "suppressed": assignment["suppressed"],
                         "suppressed_singletons":
                             assignment["suppressed_singletons"],
                         "conflicts": assignment["conflicts"]}
    except Exception as exc:
        suffix_map = {}
        # Every list key the complete branch emits must exist here too --
        # a consumer that reads report["year_suffixes"]["suppressed"] would
        # otherwise KeyError on the error path only, which is exactly the
        # path that gets the least testing.
        suffix_report = {"status": "error", "error": repr(exc), "assigned": 0,
                         "groups": [], "overflow": [], "suppressed": [],
                         "suppressed_singletons": [], "conflicts": []}
    report["year_suffixes"] = suffix_report
    # Filled in by the chunk loop below and reported on BOTH branches: these
    # two keys are attached to the dict `suffix_report` already is, so the
    # error path carries them exactly like the complete path.
    residual_neutralized: list = []
    residual_unresolved: list = []
    suffix_report["residual_neutralized"] = residual_neutralized
    suffix_report["residual_unresolved"] = residual_unresolved

    # Same by-reference trick as the two lists above, for the same two reasons:
    # the venue splice happens inside the stamping loop, long after
    # venue_report was built and attached, so the report must hold the SAME
    # list objects the loop appends to; and attaching here means the vetting
    # ERROR path carries these keys too rather than only the complete path.
    # `stamped_entries` is what `flagged_entries` deliberately is not -- a
    # count of fields that actually reached the bib.
    venue_stamped: list = []
    venue_splice_failed: list = []
    venue_report["stamped_entries"] = venue_stamped
    venue_report["splice_failed"] = venue_splice_failed

    # Same by-reference attach for the web gate's two derived fields. It must
    # happen HERE, after the web pass's json round-trip (and after its error
    # path rebuilt the dict), or the stamping loop would append to list
    # objects the report no longer holds. Attached unconditionally so the
    # ERROR path carries the keys too — a consumer must not have to guess.
    web_stamped: list = []
    web_splice_failed: list = []
    web_report["stamped_entries"] = web_stamped
    web_report["splice_failed"] = web_splice_failed

    # Build final content in memory: context fields + stamp, then bookkeeping.
    outputs = {}
    for i, d in domains.items():
        bib_name = d["bib_name"]
        e_entries = {
            k: v
            for k, v in ((d["enrichment"] or {}).get("entries", {}) or {}).items()
            if isinstance(v, dict)
        }
        report["attestations"][bib_name] = {}
        report["stamps"][bib_name] = {}
        final_chunks = []
        for chunk in parsed[i]:
            header = se.entry_header(chunk)
            if not header:
                final_chunks.append(chunk)
                continue
            etype, key = header
            cv = context_values.get((i, key))
            if cv:
                chunk = add_field_to_entry(chunk, cv[0], cv[1])
            h = healed.get((i, key))
            if h:
                pre_heal_chunk = chunk
                chunk = add_field_to_entry(chunk, "abstract", h[0])
                chunk = add_field_to_entry(chunk, "abstract_source", h[1])
                if not _heal_splice_is_well_formed(chunk):
                    # The splice did not land cleanly -- never emit a bib
                    # the real parser rejects (or a hidden duplicate
                    # field). Drop the heal: revert to the pre-splice
                    # chunk, let the entry demote via the re-derivation
                    # below, and correct the report so it never claims a
                    # restore that did not land (review finding 1b).
                    chunk = pre_heal_chunk
                    report["healed"][bib_name][key] = {
                        "outcome": "unhealed", "source": h[1]}
                    # Correct the corroboration bucket too, or the report
                    # contradicts itself -- "corroborated" beside an
                    # "unhealed" heal and a demoted stamp -- and item 15's
                    # corroborated count is inflated by restorations that
                    # never reached the bib.
                    report["abstract_corroboration"].setdefault(
                        bib_name, {})[key] = _heal_bucket(h[1], "unhealed")
            fields = se.parse_entry_fields(chunk)
            att = atts[i].get(key) or se.EntryAttestation()
            # Re-derive from the final text: the stamp must never trust a
            # flag set in the attestation loop if the corresponding splice
            # did not land in THIS chunk (fail-closed against index skew).
            # BOTH conjuncts are load-bearing, and neither implies the other:
            # ledger equality proves the text in THIS chunk is the attested
            # one, and the corroboration set proves a live fetch backed it
            # this run. Dropping the second re-grants the tier to every
            # forged ledger record the gate above just refused.
            att.abstract_attested = bool(
                se.attest_abstract(fields, e_entries.get(key))
                and (i, key) in corroborated)
            # Re-derived per chunk for the same fail-closed reason as the line
            # above: the flag is keyed (i, key), so an index skew must never
            # promote a neighbouring entry.
            att.web_gate_passed = (i, key) in web_gates
            tier = se.compute_tier(etype, fields, att)
            # venue_status is spliced AFTER tier is computed, not before: it
            # is the only field splice upstream of compute_tier, and tier
            # invariance (item 3 D) must be structural, not incidental on
            # compute_tier happening not to read this field. Splicing here
            # means it can no longer matter even if that ever changes.
            status = venue_flags.get((i, key))
            if status:
                # vv is never None here: `status` is truthy only if
                # venue_flags was populated, which happens only past the
                # `if vv is None: raise` guard. (_DERIVED_FIELD_RE above
                # must keep the literal -- it is built at import time, when
                # vv may legitimately be None.)
                pre_venue = chunk
                chunk = _stamp_optional_field(chunk, vv.VENUE_STATUS_FIELD, status)
                if _venue_splice_took(chunk, pre_venue, status):
                    venue_stamped.append(f"{bib_name}:{key}")
                else:
                    # Revert, then report. Reverting matters because one of the
                    # ways the splice fails is a DUPLICATE field, which pybtex
                    # rejects outright -- keeping that chunk would cost all of
                    # Phase 6 rather than one caveat. Reporting matters because
                    # the alternative is the silent loss this fix exists to end.
                    chunk = pre_venue
                    venue_splice_failed.append(f"{bib_name}:{key}")
            gate = web_gates.get((i, key))
            if gate:
                # Spliced AFTER compute_tier for the same reason venue_status
                # is: tier invariance under field splices stays structural
                # rather than depending on compute_tier not reading them.
                # Each splice is verified and reverted independently, like
                # its venue/year_suffix siblings — a failed urldate must not
                # cost the archiveurl, and vice versa.
                for wfield, wvalue, wre in (
                        ("urldate", gate["urldate"], _URLDATE_FIELD_RE),
                        ("archiveurl", gate["archiveurl"], _ARCHIVEURL_FIELD_RE)):
                    if not wvalue:
                        continue
                    pre_web = chunk
                    chunk = _stamp_optional_field(chunk, wfield, wvalue)
                    if _derived_field_took(chunk, pre_web, wfield, wvalue, wre):
                        web_stamped.append(f"{bib_name}:{key}:{wfield}")
                    else:
                        # Revert, then report — same two reasons as the venue
                        # path: a duplicate field would cost all of Phase 6,
                        # and a silent loss is what the gate policy forbids.
                        chunk = pre_web
                        web_splice_failed.append(f"{bib_name}:{key}:{wfield}")
            letter = suffix_map.get((i, key))
            stale = (i, key) in residual_suffix
            if letter or stale:
                # One splice, two jobs. With a letter this run is the
                # ordinary stamp, and it OVERWRITES a residual in place
                # (add_field_to_entry matches on any leading whitespace) --
                # so an entry the assigner letters is already safe. Without
                # one, the splice is the REFUSAL: the barrier owns this
                # field, it did not derive this value and cannot strip it,
                # so it overwrites it with its own decision for this entry,
                # which is "no letter".
                #
                # Note the refusal is NOT "suppress this run's letters".
                # That option was measured and is strictly worse: it removes
                # the very overwrite that cleans residuals off the entries
                # the assigner does letter, leaving MORE untrusted values
                # standing than doing nothing.
                pre_splice = chunk
                intended = letter or SUFFIX_UNTRUSTED
                chunk = _stamp_optional_field(chunk, ys.SUFFIX_FIELD, intended)
                if stale and not _splice_took(chunk, pre_splice, intended):
                    # Never emit a bib the real parser rejects, and never
                    # claim a neutralization that did not happen. Revert, and
                    # report: this is the one shape that stays a live drop
                    # hazard, so it must reach an operator.
                    chunk = pre_splice
                    residual_unresolved.append(f"{bib_name}:{key}")
                elif stale:
                    residual_neutralized.append(f"{bib_name}:{key}")
            final_chunks.append(se.stamp_entry_text(chunk, tier))
            report["stamps"][bib_name][key] = tier
            report["attestations"][bib_name][key] = _att_blob(
                att, e_entries.get(key), cv,
                web_url=(wv.normalize_url(wv.extract_url(fields) or "") or None)
                if att.web_gate_passed else None)
            qual = f"{bib_name}:{key}"
            if att.cleaning_abstained:
                report["cleaning_abstained"].append(qual)
            if tier == se.TIER_NONE:
                if (not att.api_matched or att.breaker_tripped) and (
                    fields.get("doi")
                    or (fields.get("publisher") and etype.lower() in se.CONTAINER_TYPES)
                ):
                    report["demoted_would_be_existence_v4"].append(qual)
        outputs[d["bib"]] = "\n".join(final_chunks)
    report["status"] = "degraded" if degraded else "complete"
    return report, outputs


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))


def execute(review_dir: Path, n_domains: int, debug: bool = False) -> int:
    ijson = review_dir / "intermediate_files" / "json"
    ijson.mkdir(parents=True, exist_ok=True)
    report_path = ijson / "evidence_report.json"
    outputs = {}
    try:
        report, outputs = run_barrier(review_dir, n_domains, debug=debug)
    except Exception as exc:  # crash = run-level failure; nothing was written
        report = {"schema_version": 2, "status": "failed", "error": repr(exc)}
    try:
        _atomic_write(report_path, json.dumps(report, indent=2))
        if report["status"] != "failed":
            for path, content in outputs.items():  # report first, bibs second
                _atomic_write(path, content)
    except OSError as exc:
        print(json.dumps({"status": "failed", "error": repr(exc)}))
        return 1
    tiers = {}
    for per_bib in (report.get("stamps") or {}).values():
        for t in per_bib.values():
            tiers[t] = tiers.get(t, 0) + 1
    print(json.dumps({
        "status": report["status"],
        "stamped": sum(len(v) for v in (report.get("stamps") or {}).values()),
        "tiers": tiers,
        # Replaces the flat web_sources_none count: that number could not
        # distinguish "nobody ran the fetch tool" from "the hosts were down"
        # from "the notes' spans were not on the page", which are three
        # different things for an operator to do something about.
        "web_sources": {
            "status": (report.get("web_sources") or {}).get("status", "not-run"),
            "gate_passed": (report.get("web_sources") or {}).get(
                "gate_passed", {"script": 0, "agent": 0}),
            "not_promoted": sum(
                len(v) for k, v in (report.get("web_sources") or {}).items()
                if k in ("no_capture", "no_existence", "no_url",
                         "fetch_error", "entry_error", "excluded_host")
            ) + sum(len(v) for v in ((report.get("web_sources") or {})
                                     .get("capture_rejected") or {}).values()),
            # Printed for the same reason venue_vetting's pair is: the
            # DIFFERENCE between what the gate decided and what reached the
            # bib is the finding, and a swallowed splice used to be invisible.
            "stamped_entries": len(
                (report.get("web_sources") or {}).get("stamped_entries") or []),
            "splice_failed": len(
                (report.get("web_sources") or {}).get("splice_failed") or []),
        },
        "cleaning_abstained": len(report.get("cleaning_abstained") or []),
        # Printed for the same reason the two pairs below are: the DIFFERENCE
        # between candidates and corroborated is the finding. Every
        # non-corroborated outcome demotes an entry the ledger vouched for,
        # and a demotion nobody can see is exactly what the gate policy
        # forbids -- the report names the entries, this line makes the rate
        # visible without opening it.
        "abstract_corroboration": _corroboration_summary(report),
        "venue_vetting": {
            "status": (report.get("venue_vetting") or {}).get("status", "not-run"),
            "flagged_entries": (report.get("venue_vetting") or {}).get("flagged_entries", 0),
            # Printed beside flagged_entries because the DIFFERENCE is the
            # finding: flagged is what the rule decided, stamped is what
            # reached the bib, and a gap between them used to be invisible.
            "stamped_entries": len(
                (report.get("venue_vetting") or {}).get("stamped_entries") or []),
            "splice_failed": len(
                (report.get("venue_vetting") or {}).get("splice_failed") or []),
        },
        # A bare assigned-count cannot distinguish "no same-author-same-year
        # groups existed" from "a group existed and deliberately got no
        # letters", which is the one case an operator needs to look at. The
        # counts map 1:1 onto the report keys that name the groups.
        #
        # `status` first, and for the same reason the venue summary beside it
        # carries one: WITHOUT it, an assignment that RAISED prints exactly
        # the zeros a quiet run prints, so the loudest failure this pass has
        # is the one an operator cannot see. The gate policy forbids a silent
        # failure whichever direction the gate fails in, and this pass fails
        # open by design (letters are lost, the run survives) -- which makes
        # the printed line the only place the loss surfaces at all.
        "year_suffixes": {
            "status": (report.get("year_suffixes") or {}).get("status", "not-run"),
            "assigned": (report.get("year_suffixes") or {}).get("assigned", 0),
            "overflow": len((report.get("year_suffixes") or {}).get("overflow") or []),
            "suppressed": len((report.get("year_suffixes") or {}).get("suppressed") or []),
            # The one residual shape the barrier could NOT neutralise, and
            # therefore the one an operator has to act on: a stale letter
            # this run neither derived nor could overwrite is still on disk
            # and can still license a Phase 6 drop. The neutralised ones need
            # no action and stay in the report only.
            "residual_unresolved": len(
                (report.get("year_suffixes") or {}).get("residual_unresolved") or []),
        },
        "report": str(report_path),
    }))
    return 1 if report["status"] == "failed" else 0


def main() -> int:
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv(usecwd=True), override=True)
    ap = argparse.ArgumentParser(description="Evidence barrier (Phase 3->4)")
    ap.add_argument("review_dir")
    ap.add_argument("--domains", type=int, required=True)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    return execute(Path(args.review_dir), args.domains, debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
