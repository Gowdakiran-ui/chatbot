"""Piece 5 — parent_id assignment for the Chanakya KB.

What "parent" means differs by source, because the source data itself has different
shapes:

- Verse-style sources (Arthashastra, Chanakya Neeti): chunk_verse_style buffers raw
  units (verses/paragraphs) until min_tokens is reached, so a single book+chapter is
  often split across several sibling chunks. There's no single pre-existing chunk that
  "is" the chapter — parent_id here is a *group key* (not another chunk's id); the
  retrieval-side expansion function (db/parent_expansion.py) concatenates every sibling
  chunk that shares it, in original sequence order.
  - Arthashastra references are "Book X, Chapter Y" (no verse numbers) — grouping by
    chapter alone naturally clusters ~4-5 sibling chunks (151 distinct refs / 731 chunks).
  - Chanakya Neeti references are "Chapter X, Verse X.Y" — almost every chunk has a
    distinct verse number (306 distinct refs / 309 chunks), so grouping must drop the
    verse component and use chapter alone to produce any meaningful multi-chunk parent.
- Prose sources (Corporate Chanakya, 7 Secrets of Leadership, chanakya_info bio): each
  chunk already has a unique "segment N" reference — there is no book/chapter/section
  grouping metadata in these sources to group chunks under, so a group-key parent_id
  would be meaningless (every "group" would have exactly one member). parent_id is None
  for these; the retrieval-side expansion instead pulls in the adjacent segment(s) as a
  neighbor window, since chunk_prose_style already chunks these into paragraph/section-
  sized pieces in strict source order.
"""
from __future__ import annotations

import re

_BOOK_RE = re.compile(r"Book\s+([IVXLCDM]+)", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"Chapter\s+([IVXLCDM\d]+)", re.IGNORECASE)


def chapter_group_key(source: str, reference: str) -> str | None:
    """The first Book/Chapter mentioned in `reference` (ignores verse numbers and the
    second half of an en-dash range) — deliberately coarse so a chunk that legitimately
    spans two chapters still groups with its first chapter's siblings. Returns None if
    the reference has no recognizable book/chapter structure (e.g. "untitled")."""
    book_m = _BOOK_RE.search(reference)
    chapter_m = _CHAPTER_RE.search(reference)
    if not book_m and not chapter_m:
        return None

    parts = [source]
    if book_m:
        parts.append(f"book_{book_m.group(1).lower()}")
    if chapter_m:
        parts.append(f"chapter_{chapter_m.group(1).lower()}")
    return "_".join(parts)


def compute_parent_id(row: dict) -> str | None:
    """row: a chanakya_kb.jsonl record (id, source, chunk_type, reference, ...)."""
    if row["chunk_type"] != "verse":
        return None
    return chapter_group_key(row["source"], row["reference"])
