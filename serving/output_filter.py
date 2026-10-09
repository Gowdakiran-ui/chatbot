"""Output-side backstops for generated answers (quality-fix plan, Step 1).

Prompts are only a request, so these are deterministic checks that run on what
the model actually produced:

- `ChunkIdStripper`: removes chunk ids (e.g. "[america_case_009_went_right]") from
  the token stream before the client sees them. Streaming-safe: tokens can split an
  id in half, so text is only released up to the last whitespace and the trailing
  partial word is held until it completes.
- `verse_refs_not_in_context`: detection only. Returns verse-style references
  ("7.5.19", "1.8.25-26") in an answer that appear in none of the supplied chunks.
"""
from __future__ import annotations

import re
from typing import Iterable

_GENERIC_ID_RE = re.compile(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_(?:case_\d+|segment_\d+|chapter_\w+|book_\w+)\w*")
_DANGLING_SEPARATOR_RE = re.compile(r"\s+/\s+(?=and\b|[,.;:)])")
_EMPTY_BRACKETS_RE = re.compile(r"\s*[\[(]\s*[\])]")
_VERSE_REF_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{1,3}(?:\s*[-–]\s*\d{1,3})?\b")


def strip_chunk_ids(text: str, known_ids: Iterable[str] = ()) -> str:
    """Remove chunk ids (plus the brackets/parentheses wrapped around them) from `text`."""
    alternatives = [re.escape(i) for i in sorted(set(known_ids), key=len, reverse=True)]
    id_pattern = "|".join(alternatives + [_GENERIC_ID_RE.pattern])
    wrapped = re.compile(rf"\s*[\[(]\s*(?:{id_pattern})\s*[\])]|(?<![\w/])(?:{id_pattern})(?![\w])")
    cleaned = wrapped.sub("", text)
    cleaned = _EMPTY_BRACKETS_RE.sub("", cleaned)
    return _DANGLING_SEPARATOR_RE.sub("", cleaned)


class ChunkIdStripper:
    """Feed streamed tokens in, get id-free text out.

    Tokens pass straight through unless the trailing word could be the start of an id
    (it contains "_" or "[", or opens a "(" it has not closed) - that word is held until
    it completes, so a token boundary can never split an id in half.
    """

    def __init__(self, known_ids: Iterable[str] = ()) -> None:
        self._known_ids = tuple(known_ids)
        self._pending = ""
        self._last_char = ""
        self._removed_last = False

    def _hold_start(self) -> int:
        word_start = max(self._pending.rfind(" "), self._pending.rfind("\n")) + 1
        word = self._pending[word_start:]
        if "_" in word or "[" in word or ("(" in word and ")" not in word):
            return word_start
        return len(self._pending)

    def _emit(self, ready: str) -> str:
        cleaned = strip_chunk_ids(ready, self._known_ids)
        # Removing an id between two spaces would leave a doubled space; trim it, but only
        # right after a removal so intentional markdown double-spaces survive.
        removed_now = len(cleaned) < len(ready)
        if (self._removed_last or removed_now) and cleaned.startswith(" ") and self._last_char in (" ", ""):
            cleaned = cleaned.lstrip(" ")
        self._removed_last = removed_now
        if cleaned:
            self._last_char = cleaned[-1]
        return cleaned

    def feed(self, token: str) -> str:
        self._pending += token
        cut = self._hold_start()
        ready, self._pending = self._pending[:cut], self._pending[cut:]
        return self._emit(ready)

    def flush(self) -> str:
        ready, self._pending = self._pending, ""
        return self._emit(ready)


def verse_refs_not_in_context(answer: str, context_texts: Iterable[str]) -> list[str]:
    context = "\n".join(context_texts)
    missing: list[str] = []
    for ref in dict.fromkeys(_VERSE_REF_RE.findall(answer)):
        first = re.split(r"\s*[-–]\s*", ref)[0]
        if first not in context:
            missing.append(ref)
    return missing
