"""abstract_usability: the barrier's second abstract test.

The positive cases are the five corroborated-but-unusable abstracts from the
2026-09-10 separation-of-powers run (PL-5). The negative controls are the
near misses the rules were refined on, from the local corpus measurement
(docs/known-issues/abstract-usability-measurement-2026-10-02/README.md).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "literature-review" / "scripts"))
import abstract_usability as au  # noqa: E402

GRANLUND = {
    "title": "Electoral accountability in a country with two-tiered government",
    "author": "Granlund, David", "journal": "Public Choice"}
MCCUBBINS = {
    "title": "Administrative Procedures as Instruments of Political Control",
    "author": "McCubbins, Mathew D. and Noll, Roger G. and Weingast, Barry R.",
    "journal": "The Journal of Law, Economics, and Organization"}
KATYAL = {
    "title": "Internal Separation of Powers: Checking Today's Most Dangerous Branch from Within",
    "author": "Katyal, Neal Kumar", "journal": "The Yale Law Journal"}
BAROS = {
    "title": "Unpacking the separation of powers",
    "author": "Baroš, Jiří and Dufek, Pavel and Kosař, David",
    "booktitle": "New Challenges to the Separation of Powers",
    "publisher": "Edward Elgar Publishing"}
SKACH = {
    "title": "The ``Newest'' Separation of Powers: Semipresidentialism",
    "author": "Skach, C.", "journal": "International Journal of Constitutional Law"}

BAROS_TEXT = (
    "Separation of powers has returned to the forefront of both public and "
    "scholarly attention, with countries of Central Europe providing ample "
    "material for reflection. Recent political developments in Hungary and "
    "Poland have reminded us that the tripartite division of state power among "
    "legislative, executive and judiciary remains vulnerable to whims of power, "
    "and that aggressive pursuit of self-contained goals by the executive may "
    "quickly disrupt the delicate balance among the highest bodies in a "
    "constitutional democracy. Be it Viktor Orbán’s “constitutional "
    "blitzkrieg” which resulted in Fidesz’s government subjugating both the "
    "judiciary (including the Constitutional Court) and numerous independent "
    "state agencies, or similar domination by Jaroslav Kaczyński’s Law and "
    "Justice party over the judicial system in Poland – we have some almost "
    "first-hand experience of what happens once a populist leader perceives "
    "the principle2 of separation of powers as an obstacle which prevents him "
    "from centralising power and running the country as he sees fit.3")

# The last 160 words of skach2007newest's 4,721-word "abstract": an OpenAlex
# full text whose content words have dropped out.
SKACH_TAIL = (
    "presidential the and at the to or other that as constitutional such as a "
    "constitutional But this that a has this and is not to a popularly elected "
    "for or historical This also that is political for constitutional “the "
    "political often to that are for some and for on who has the to their are "
    "no and semipresidentialism to that to presidential and the in the of "
    "political and and for in and may be to is a for constitutional this "
    "constitution also various on and on a is in constitutional and the issue "
    "is to constitutional into a comparative historical of constitutional "
    "structures and as have to the of the model the or of this new of the "
    "separation of powers. we not with us the of new for political with "
    "democratic have a on the of the that existing can a of the of and that "
    "countries with or can in be in no on the of for")

# Real prose, ~130 words, to build controls from.
PROSE = (
    "Political constitutions are incomplete contracts and therefore leave room "
    "for abuse of power. In democracies, elections are the primary mechanism "
    "for disciplining public officials, but they are not sufficient. Separation "
    "of powers between executive and legislative bodies can improve the "
    "accountability of elected officials and constrain the rents they extract, "
    "but only with appropriate checks and balances. We show that a model of "
    "legislative bargaining with voters who observe outcomes but not actions "
    "yields precise predictions about which institutional arrangements reduce "
    "rents, and we compare presidential and parliamentary regimes on that "
    "basis. The analysis explains why presidential regimes have smaller "
    "governments and why parliamentary regimes redistribute more broadly, and "
    "it derives testable implications for cross-country work on fiscal "
    "policy, corruption and the size of the public sector.")


@pytest.mark.parametrize("text, fields, reason", [
    ("Moral hazard, Separation of powers, Stackelberg, Transparency, Voting "
     "theory, D72, H00, H77,", GRANLUND, "too-thin"),
    ("MATHEW D. MCCUBBINS, ROGER G. NOLL, BARRY R. WEINGAST; Administrative "
     "Procedures as Instruments of Political Control, The Journal of Law, "
     "Economics, and Or", MCCUBBINS, "too-thin"),
    ("Neal Kumar Katyal, Internal Separation of Powers: Checking Today's Most "
     "Dangerous Branch from Within, The Yale Law Journal, Vol. 115, No. 9, The "
     "Most Dangerous Branch? Mayors, Governors, Presidents, and the Rule of "
     "Law: A Symposium on Executive Power (2006), pp. 2314-2349", KATYAL,
     "too-thin"),
    (BAROS_TEXT, BAROS, "body-text"),
    (PROSE + " " + SKACH_TAIL, SKACH, "garbled"),
])
def test_the_five_corroborated_but_unusable_abstracts_are_refused(text, fields, reason):
    assert au.unusable_reason(text, fields) == reason


def test_prose_passes():
    assert au.unusable_reason(PROSE, {"title": "Separation of Powers and Political Accountability"}) is None


@pytest.mark.parametrize("marker", au.PAGE_CHROME)
def test_every_page_chrome_marker_refuses_a_text_with_prose_around_it(marker):
    text = PROSE + " " + marker.upper() + " " + PROSE
    assert au.unusable_reason(text, {}) == "page-chrome"


def test_the_citation_fields_are_what_a_stub_is_thin_against():
    """The same stub is thin against its own entry and not against a
    stranger's: the residual removes the ENTRY's citation, not words
    in general."""
    stub = ("Mathew McCubbins, Roger Noll, Barry Weingast: Administrative "
            "Procedures as Instruments of Political Control. Journal of Law, "
            "Economics, and Organization, volume three, number two, pages "
            "243 to 277, published by Oxford University Press.")
    assert au.unusable_reason(stub, MCCUBBINS) == "too-thin"
    assert au.residual_words(stub, {}) >= au.MIN_RESIDUAL_WORDS


@pytest.mark.parametrize("text", [
    # a variable name, not footnote calls (plumper2010level)
    "The polity2 variable from the Polity IV project is the most popular "
    "measure of a country's political regime. This article contends that the "
    "coding rules employed to create a polity2 score produce a measure that "
    "lacks face validity. We recommend that scholars using polity2 test "
    "whether results are robust, or justify polity2 explicitly.",
    # a contents list after a real abstract, numbers after heading words
    # (tal2016making)
    PROSE + " 1 Introduction2 Making Time Universal 2.1 Stability and accuracy "
    "2.5 The leap second3 The Two Faces of Stability 3.1 An explanatory "
    "challenge 3.3 Constructivist explanations4 Models and Standardization "
    "4.6 Remark on scope5 Conclusions",
    # a contents list whose numbers are followed by a period
    # (schaffer2007deterministic)
    PROSE + " 1. Overview2. Four Arguments for Deterministic Chance3. Four "
    "Conceptions of Deterministic Chance4. The Role of Chance5. Epistemic Chance",
    # one footnote call only
    PROSE + " as Frankfurt noted.1",
])
def test_footnote_shaped_text_that_is_not_a_footnote_run_passes(text):
    assert au.unusable_reason(text, {}) is None


def test_a_repeated_number_is_never_a_footnote_run():
    """Only the distinctness test decides here: both calls follow a period
    and their numbers are in order, but footnotes do not repeat."""
    assert au.footnote_calls("results for the alpha.2 and for the alpha.2 again") == 0
    assert au.footnote_calls("results for the alpha.1 and for the beta.2 again") == 2


def test_a_long_footnoted_full_text_is_not_an_opening_extract():
    """Footnote calls in a text of MAX_EXTRACT_WORDS or more: most of the
    work itself, which a writer can characterize it from."""
    long_text = " ".join([PROSE] * 9)
    long_text = long_text.replace("power.", "power.1", 1).replace(
        "sufficient.", "sufficient.2", 1).replace("balances.", "balances.3", 1)
    assert len(au._words(long_text)) >= au.MAX_EXTRACT_WORDS
    assert au.footnote_calls(long_text) == 3   # a real run: only the length passes it
    assert au.unusable_reason(long_text, {}) is None
    # the same calls in an extract under the bound are refused
    short = PROSE.replace("power.", "power.1", 1).replace(
        "sufficient.", "sufficient.2", 1)
    assert au.unusable_reason(short, {}) == "body-text"


@pytest.mark.parametrize("text", [
    "Suppose that you prefer A to B, B to C, and C to A. Your preferences "
    "violate Expected Utility Theory by being cyclic. Suppose that you start "
    "with A. Then you should be willing to trade A for C and then C for B. "
    "Since you prefer A to B, you pay the small sum to trade from B to A. "
    "This Element shows how each of the axioms can be defended by money-pump "
    "arguments of this kind, and what that implies for rational choice.",
    "Cronbach's a is the most widely used index of the reliability of a "
    "scale. This article discusses the historical development of a from other "
    "indexes and four myths associated with a: (a) that it is a fixed "
    "property, (b) that it measures only internal consistency, (c) that "
    "higher values are always preferred, and (d) that it is restricted to the "
    "range of 0 to 1. It recommends acceptable values of a in practice.",
])
def test_a_variable_named_a_is_not_word_salad(text):
    assert au.garble_hits(text) < au.MIN_GARBLE_HITS
    assert au.unusable_reason(text, {}) is None


@pytest.mark.parametrize("text", [
    "Η δημοκρατία είναι ένα πολίτευμα στο οποίο η εξουσία ανήκει στον λαό, "
    "ο οποίος την ασκεί είτε άμεσα είτε μέσω εκλεγμένων αντιπροσώπων που "
    "λογοδοτούν σε τακτές εκλογές και υπόκεινται σε θεσμικούς ελέγχους.",
    "Демократия — это политический режим, при котором власть принадлежит "
    "народу, осуществляющему её непосредственно или через избранных "
    "представителей, подотчётных избирателям и ограниченных разделением властей.",
    "民主主义是一种政治制度，人民通过选举代表来行使权力，并通过分权制衡来限制政府。",
])
def test_non_latin_abstracts_are_counted_not_read_as_empty(text):
    assert au.unusable_reason(text, {}) is None


def test_empty_and_missing_text_are_too_thin():
    assert au.unusable_reason("", {}) == "too-thin"
    assert au.unusable_reason(None, {}) == "too-thin"
