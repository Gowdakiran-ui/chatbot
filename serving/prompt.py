"""Builds the user-turn prompt handed to generation, from the deduped/budgeted
chunks in a RetrievalResult (Piece 3) — the system prompt (Piece 2) is loaded and
passed separately, per providers.base.GenerationProvider's generate(prompt, system, stream)."""
from __future__ import annotations

from serving.retrieval import RetrievalResult


def build_prompt(query: str, result: RetrievalResult) -> str:
    context_block = "\n\n---\n\n".join(f"[{chunk.chunk_id}]\n{chunk.text}" for chunk in result.chunks)
    return f"Retrieved context:\n\n{context_block}\n\nQuestion: {query}"
