"""Generation-quality fixes task, Fix 2 — soft groundedness check.

Detection only, never blocks or alters the response — same philosophy as
serving/injection_check.py. A false positive here (flagging a genuinely grounded
answer) is far cheaper than a false block on a real user's turn, so this errs
toward flagging rather than trying to be precise.

Deliberately cheap and local — no extra LLM call. Extracts candidate "specific
named things" from the generated answer (markdown-italicized terms, capitalized
multi-word phrases, and multi-word quoted spans) and checks whether each appears
somewhere in the concatenated retrieved context; terms with no match are flagged
as possible ungrounded embellishment — content drawn from the model's own
pretraining rather than the retrieved passages, which every system prompt in
this project explicitly forbids.

This targets a specific, real failure mode found in a live eval
(preprocessing/tests/eval_generation.py, see eval_report.md): asked about a
modern business-book anecdote, the model framed it using Chanakya lore it
already knew — "rajarshi", "the Arthashastra" — despite neither term appearing
anywhere in the retrieved passages. Both are markdown-italicized in the model's
own output (its convention for a term it's treating as authoritative/technical),
which is why italics are one of the three extraction patterns here, not just
capitalized phrases. This won't catch paraphrased ungrounded claims that don't
surface as a distinct named term — that's a harder problem, out of scope here.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

# A markdown-italic span using single asterisks — *word* or *multi word phrase*
# — but not a **bold** span, which also uses asterisks. The lookaround pairs
# ensure we match a lone "*", not one side of a "**".
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]{2,60}?)(?<!\*)\*(?!\*)")

# Two to four consecutive capitalized words — a lightweight proxy for named
# entities/concepts (company names, act names, titles) without an NLP dependency.
_CAPITALIZED_PHRASE_RE = re.compile(r"\b(?:[A-Z][a-zA-Z']+\s+){1,3}[A-Z][a-zA-Z']+\b")

# Quoted spans of 2+ words, single or "curly" double quotes.
_QUOTED_TERM_RE = re.compile(r'["“]([A-Za-z][\w\s\'-]{2,60}?)["”]')

# Leading article/title words that make an otherwise-grounded entity fail a
# literal substring check (context says "Punjab National Bank", the model
# writes "The Punjab National Bank" or "CEO John Stumpf") — found live during
# this task's own re-verification run. Stripped before the containment check;
# the original term (with the prefix) is still what gets reported if flagged.
_LEADING_STOPWORDS = ("the ", "a ", "an ", "both ", "ceo ", "mr ", "mr. ", "ms ", "ms. ", "dr ", "dr. ")


class GroundednessResult(BaseModel):
    query: str
    flagged: bool
    flagged_terms: list[str]


def _extract_candidate_terms(answer: str) -> list[str]:
    terms: set[str] = set()
    for match in _ITALIC_RE.finditer(answer):
        terms.add(match.group(1).strip())
    for match in _CAPITALIZED_PHRASE_RE.finditer(answer):
        terms.add(match.group(0).strip())
    for match in _QUOTED_TERM_RE.finditer(answer):
        term = match.group(1).strip()
        if len(term.split()) >= 2:
            terms.add(term)
    return sorted(t for t in terms if t)


def _is_grounded(term: str, context: str) -> bool:
    lowered = term.lower()
    if lowered in context:
        return True
    for prefix in _LEADING_STOPWORDS:
        if lowered.startswith(prefix):
            remainder = lowered[len(prefix) :]
            return bool(remainder) and remainder in context
    return False


def check_groundedness(answer: str, retrieved_texts: list[str], query: str = "") -> GroundednessResult:
    """Flags candidate terms in `answer` that don't appear (case-insensitively)
    anywhere in `retrieved_texts`. Cheap substring matching, not semantic — noisy
    by design (see module docstring); every flag is meant for human/log review,
    not automated action.

    `retrieved_texts` should include everything the model actually saw for this
    turn — not just each chunk's body text, but also its chunk_id, since
    serving/prompt.py shows the model a "[chunk_id]" header per chunk and a
    citation can be legitimately derived from that (e.g. chunk_id
    "arthashastra_book_viii_chapter_iv_001" grounds a "Book VIII, Chapter IV"
    citation) without appearing in the body text at all."""
    context = " ".join(retrieved_texts).lower()
    flagged_terms = [term for term in _extract_candidate_terms(answer) if not _is_grounded(term, context)]
    return GroundednessResult(query=query, flagged=bool(flagged_terms), flagged_terms=flagged_terms)
