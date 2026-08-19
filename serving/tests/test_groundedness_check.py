import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

from serving.groundedness_check import check_groundedness


def test_flags_italicized_term_absent_from_context():
    answer = "This is the conduct of a *rajarshi*, a sage-like king."
    context = ["The businessman thanked Mr Chheda for the loan."]

    result = check_groundedness(answer, context)

    assert result.flagged is True
    assert "rajarshi" in result.flagged_terms


def test_flags_capitalized_arthashastra_reference_absent_from_context():
    answer = "This is the alliance-building I prescribed in the *Arthashastra*."
    context = ["Mr Chheda gave the businessman a cheque to rebuild his company."]

    result = check_groundedness(answer, context)

    assert result.flagged is True
    assert any("arthashastra" in t.lower() for t in result.flagged_terms)


def test_does_not_flag_terms_present_in_context():
    answer = "As I taught in the *Arthashastra*, Book VIII, Chapter IV, pestilence devastates only part of a country."
    context = [
        "GROUP OF OBSTRUCTIONS... My teacher says that of pestilence and famine... "
        "the Arthashastra, Book VIII, Chapter IV explains providential calamities."
    ]

    result = check_groundedness(answer, context)

    assert result.flagged is False
    assert result.flagged_terms == []


def test_does_not_flag_bold_markdown_headers():
    """A real false-positive source found during development: naive italic
    matching picks up **bold** spans too, since ** looks like two single-*
    delimiters. Bold section headers (a normal formatting choice, not an
    ungrounded claim) must not be flagged just for being unmatched in context."""
    answer = "**Reputational impact.** The damage was severe and lasted for years."
    context = ["Some retrieved case text with none of these exact words."]

    result = check_groundedness(answer, context)

    assert "Reputational impact." not in result.flagged_terms


def test_real_pnb_case_study_produces_no_flags_for_grounded_entities():
    """Regression-style test using a trimmed version of a real eval answer
    (Nirav Modi / PNB) verified fully grounded — entities genuinely present in
    context must not be flagged."""
    answer = (
        "This case, involving Nirav Modi and Punjab National Bank in 2018, is a banking fraud. "
        "Total liability reached *Rupees 14,356.84 crore* (~$2 billion). "
        "Mehul Choksi was arrested in Belgium in 2025."
    )
    context = [
        "Company: Punjab National Bank (Nirav Modi / Mehul Choksi fraud). Year: 2018. "
        "Estimated Impact: Total liability reached Rupees 14,356.84 crore (~$2 billion). "
        "Mehul Choksi was arrested in Belgium in 2025."
    ]

    result = check_groundedness(answer, context)

    assert result.flagged_terms == []


def test_leading_article_prefix_does_not_cause_false_positive():
    """Real false positive found live: context says "Punjab National Bank", the
    model writes "The Punjab National Bank" — the leading article alone
    shouldn't make an otherwise-grounded entity get flagged."""
    answer = "The Punjab National Bank case is well documented."
    context = ["Company: Punjab National Bank. Year: 2018."]

    result = check_groundedness(answer, context)

    assert result.flagged_terms == []


def test_leading_title_prefix_does_not_cause_false_positive():
    answer = "CEO John Stumpf was removed following the scandal."
    context = ["John Stumpf was the CEO at the time and was later removed."]

    result = check_groundedness(answer, context)

    assert result.flagged_terms == []


def test_chunk_id_alone_grounds_a_derived_citation():
    """build_prompt() shows the model a "[chunk_id]" header per chunk — a
    citation can be legitimately derived from the id alone (e.g.
    "arthashastra_book_viii_chapter_iv_001" -> "Book VIII, Chapter IV") even
    when the body text never repeats it verbatim. Callers are expected to pass
    chunk_id (underscores replaced with spaces) alongside body text."""
    answer = "As I taught in the Arthashastra, Book VIII, Chapter IV, pestilence devastates only part of a country."
    body_text = "My teacher says that of pestilence and famine, pestilence brings all business to a stop."
    chunk_id_as_text = "arthashastra book viii chapter iv 001"

    result = check_groundedness(answer, [body_text, chunk_id_as_text])

    assert result.flagged_terms == []


def test_empty_answer_and_context_do_not_error():
    result = check_groundedness("", [])
    assert result.flagged is False
    assert result.flagged_terms == []


def test_query_is_carried_through_to_result():
    result = check_groundedness("some *term* here", ["context"], query="a test query")
    assert result.query == "a test query"
