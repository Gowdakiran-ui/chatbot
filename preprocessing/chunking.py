"""Step 2 — chunking strategies. Pure functions: no file I/O, no network calls.

`chunk_verse_style` and `chunk_prose_style` both take raw cleaned text and return a list of
`TextChunk` (text + reference + token_count). Callers (build_kb.py) attach id/source/chunk_type.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from config import MIN_VERSE_TOKENS, PROSE_OVERLAP_RATIO, PROSE_TARGET_MAX_TOKENS, PROSE_TARGET_MIN_TOKENS
from tokens import count_tokens


@dataclass(frozen=True)
class TextChunk:
    text: str
    reference: str
    token_count: int


# ---------------------------------------------------------------------------
# A. Verse / sutra-based chunking
# ---------------------------------------------------------------------------

_BOOK_RE = re.compile(r"^Book\s+([IVXLCDM]+|\d+)\b", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLCDM]+|\d+)\b\.?\s*(.*)$", re.IGNORECASE)
_VERSE_NUM_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)?)\s*$")


def _build_ref(book: str | None, chapter: str | None, verse: str | None) -> str:
    parts = []
    if book:
        parts.append(f"Book {book}")
    if chapter:
        parts.append(f"Chapter {chapter}")
    if verse:
        parts.append(f"Verse {verse}")
    return ", ".join(parts) if parts else "untitled"


@dataclass
class _RawUnit:
    text: str
    reference: str


def _split_into_raw_units(text: str) -> list[_RawUnit]:
    """First pass: split on book/chapter markers and explicit verse numbers. Where no
    explicit verse numbering exists for a stretch of text, fall back to blank-line-separated
    paragraphs as pseudo-verse boundaries (one teaching per short paragraph)."""
    units: list[_RawUnit] = []
    book: str | None = None
    chapter: str | None = None
    verse_num: str | None = None
    current_ref: str = _build_ref(None, None, None)
    buf: list[str] = []

    def flush() -> None:
        joined = "\n".join(buf).strip()
        buf.clear()
        if joined:
            units.append(_RawUnit(text=joined, reference=current_ref))

    for raw_line in text.split("\n"):
        stripped = raw_line.strip()

        book_m = _BOOK_RE.match(stripped)
        if book_m:
            flush()
            book, chapter, verse_num = book_m.group(1), None, None
            current_ref = _build_ref(book, chapter, verse_num)
            continue

        chapter_m = _CHAPTER_RE.match(stripped)
        if chapter_m:
            flush()
            chapter, verse_num = chapter_m.group(1), None
            current_ref = _build_ref(book, chapter, verse_num)
            continue

        verse_m = _VERSE_NUM_RE.match(stripped)
        if verse_m:
            flush()
            verse_num = verse_m.group(1)
            current_ref = _build_ref(book, chapter, verse_num)
            continue

        if not stripped:
            if verse_num is None:
                # No active explicit numbering: blank line marks a pseudo-verse boundary.
                flush()
            continue

        buf.append(raw_line)

    flush()
    return units


def _refs_overlap(a: str, b: str) -> bool:
    """True if one ref is a hierarchical prefix of the other (e.g. "Book II" is a
    prefix of "Book II, Chapter I") — same location described at different
    granularity, not a genuine range, so joining them with an en-dash would be
    misleading (e.g. "Book II–Book II, Chapter I")."""
    return a == b or a.startswith(b + ", ") or b.startswith(a + ", ")


def _join_refs(refs: list[str]) -> str:
    deduped = list(dict.fromkeys(refs))

    collapsed: list[str] = []
    for ref in deduped:
        if collapsed and _refs_overlap(collapsed[-1], ref):
            # Keep whichever is more specific (longer) rather than concatenating both.
            if len(ref) > len(collapsed[-1]):
                collapsed[-1] = ref
        else:
            collapsed.append(ref)

    if len(collapsed) == 1:
        return collapsed[0]
    return f"{collapsed[0]}–{collapsed[-1]}"


def chunk_verse_style(text: str, min_tokens: int = MIN_VERSE_TOKENS) -> list[TextChunk]:
    raw_units = _split_into_raw_units(text)
    if not raw_units:
        return []

    chunks: list[TextChunk] = []
    buf_text: list[str] = []
    buf_refs: list[str] = []

    def buf_token_count() -> int:
        return count_tokens("\n".join(buf_text))

    for unit in raw_units:
        buf_text.append(unit.text)
        buf_refs.append(unit.reference)
        if buf_token_count() >= min_tokens:
            joined = "\n".join(buf_text)
            chunks.append(TextChunk(text=joined, reference=_join_refs(buf_refs), token_count=count_tokens(joined)))
            buf_text, buf_refs = [], []

    if buf_text:
        # Trailing small remainder: merge into the previous chunk rather than emitting a
        # too-tiny final chunk, per "merge with 1-2 adjacent verses" guidance.
        joined = "\n".join(buf_text)
        if chunks:
            prev = chunks.pop()
            merged_text = prev.text + "\n" + joined
            merged_ref = _join_refs([prev.reference, *buf_refs])
            chunks.append(TextChunk(text=merged_text, reference=merged_ref, token_count=count_tokens(merged_text)))
        else:
            chunks.append(TextChunk(text=joined, reference=_join_refs(buf_refs), token_count=count_tokens(joined)))

    return chunks


# ---------------------------------------------------------------------------
# B. Prose-based, recursive chunking
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_if_too_large(unit: str, max_tokens: int) -> list[str]:
    """Recursive splitter: paragraph already assumed; try \\n, then sentence boundaries.
    Never splits mid-sentence."""
    if count_tokens(unit) <= max_tokens:
        return [unit]

    lines = [l for l in unit.split("\n") if l.strip()]
    if len(lines) > 1:
        result: list[str] = []
        for line in lines:
            result.extend(_split_if_too_large(line, max_tokens))
        return result

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(unit) if s.strip()]
    if len(sentences) > 1:
        return _pack_sentences(sentences, max_tokens)

    # A single sentence/line larger than max_tokens: cannot split without breaking
    # mid-sentence, so keep it whole.
    return [unit]


def _pack_sentences(sentences: list[str], max_tokens: int) -> list[str]:
    packed: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for s in sentences:
        s_tokens = count_tokens(s)
        if current and current_tokens + s_tokens > max_tokens:
            packed.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(s)
        current_tokens += s_tokens
    if current:
        packed.append(" ".join(current))
    return packed


def _pack_units(
    units: list[str], min_tokens: int, max_tokens: int
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for u in units:
        u_tokens = count_tokens(u)
        if current and current_tokens + u_tokens > max_tokens:
            chunks.append("\n\n".join(current))
            current, current_tokens = [], 0
        current.append(u)
        current_tokens += u_tokens
        if current_tokens >= min_tokens:
            chunks.append("\n\n".join(current))
            current, current_tokens = [], 0
    if current:
        joined = "\n\n".join(current)
        if chunks:
            # Trailing remainder smaller than min_tokens: merge into previous chunk.
            chunks[-1] = chunks[-1] + "\n\n" + joined
        else:
            chunks.append(joined)
    return chunks


def _add_overlap(chunk_texts: list[str], ratio: float) -> list[str]:
    if len(chunk_texts) <= 1:
        return chunk_texts

    result = [chunk_texts[0]]
    for i in range(1, len(chunk_texts)):
        prev = chunk_texts[i - 1]
        target_overlap_tokens = int(count_tokens(prev) * ratio)
        if target_overlap_tokens <= 0:
            result.append(chunk_texts[i])
            continue
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(prev) if s.strip()]
        overlap_sentences: list[str] = []
        acc = 0
        for s in reversed(sentences):
            overlap_sentences.insert(0, s)
            acc += count_tokens(s)
            if acc >= target_overlap_tokens:
                break
        overlap_text = " ".join(overlap_sentences)
        result.append(f"{overlap_text}\n\n{chunk_texts[i]}" if overlap_text else chunk_texts[i])
    return result


def chunk_prose_style(
    text: str,
    min_tokens: int = PROSE_TARGET_MIN_TOKENS,
    max_tokens: int = PROSE_TARGET_MAX_TOKENS,
    overlap_ratio: float = PROSE_OVERLAP_RATIO,
) -> list[TextChunk]:
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    units: list[str] = []
    for para in paragraphs:
        units.extend(_split_if_too_large(para, max_tokens))

    packed = _pack_units(units, min_tokens, max_tokens)
    overlapped = _add_overlap(packed, overlap_ratio)

    return [
        TextChunk(text=t, reference=f"segment {i + 1}", token_count=count_tokens(t))
        for i, t in enumerate(overlapped)
    ]
