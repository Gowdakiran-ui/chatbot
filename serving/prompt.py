"""Builds the user-turn prompt handed to generation, from the deduped/budgeted
chunks in a RetrievalResult (Piece 3) — the system prompt is loaded and passed
separately, per providers.base.GenerationProvider's generate(prompt, system, stream).

Each source is introduced by a neutral header (what it is and what kind of text it is) and never by an
internal chunk id: ids were being echoed into answers, and the old "Retrieved context" wording leaked
into the persona. `describe` maps a chunk to (label, kind); it comes from the mode's source_info_fn.
"""
from __future__ import annotations

from typing import Callable

from serving.retrieval import RetrievalResult

Describe = Callable[[dict], tuple[str, str]]


def _default_describe(payload: dict) -> tuple[str, str]:
    return str(payload.get("source") or "Source"), ""


def build_prompt(query: str, result: RetrievalResult, describe: Describe = _default_describe) -> str:
    blocks = []
    for chunk in result.chunks:
        label, kind = describe(chunk.payload)
        header = f"### {label}" + (f" ({kind})" if kind else "")
        blocks.append(f"{header}\n{chunk.text}")
    material = "\n\n---\n\n".join(blocks)
    return f"Source material for this question:\n\n{material}\n\nQuestion: {query}"
