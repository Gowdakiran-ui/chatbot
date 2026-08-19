"""Piece 3 — retrieval + parent-expansion wiring.

Calls db/hybrid_query.py's hybrid_search() against the mode's collection, expands
each hit to its fuller parent context via the mode's expand_fn (db/parent_expansion.py),
dedupes hits that expand to the same parent, and caps the total text handed to
generation at MAX_CONTEXT_CHARS.

Score note (see serving/mode_config.py's docstring for the full finding): the RRF
fused score hybrid_search() returns is rank-based and does not reliably separate
relevant from irrelevant queries — spot-checked on both live clusters. This module
attaches a `dense_score` (cosine similarity, 0-1) to every hit alongside the fused
`score`, computed against the same point's own dense vector, so Piece 4's floor
check has a number that actually reflects relevance. `RetrievalResult.top_dense_score`
is what that floor check should read — not `top_score`.
"""
from __future__ import annotations

from pydantic import BaseModel
from qdrant_client.models import Filter

from db.config import DENSE_VECTOR_NAME
from db.embedding import embed_query
from db.hybrid_query import hybrid_search
from serving.config import MAX_CONTEXT_CHARS, PREFETCH_LIMIT
from serving.mode_config import Mode, ModeConfig


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RawHit(BaseModel):
    """One hit exactly as hybrid_search returned it, before dedup/expansion/budget
    — kept in full for logging and for the floor check, which must see the true
    top hit even if it later gets dropped (e.g. as a dedup loser)."""

    chunk_id: str
    score: float  # RRF fused score — ranking signal only, see module docstring
    dense_score: float  # cosine similarity — what the floor check should use


class RetrievedChunk(BaseModel):
    """One deduped, expanded chunk of context, ready to hand to generation."""

    chunk_id: str
    score: float
    dense_score: float
    text: str
    payload: dict


class RetrievalResult(BaseModel):
    query: str
    mode: Mode
    raw_hits: list[RawHit]
    chunks: list[RetrievedChunk]

    @property
    def top_score(self) -> float:
        return self.raw_hits[0].score if self.raw_hits else 0.0

    @property
    def top_dense_score(self) -> float:
        return self.raw_hits[0].dense_score if self.raw_hits else 0.0


def retrieve_context(
    query: str, config: ModeConfig, mode: Mode, query_filter: Filter | None = None
) -> RetrievalResult:
    client = config.get_client()

    hits = hybrid_search(
        client,
        config.collection_alias,
        query,
        top_k=config.top_k,
        prefetch_limit=PREFETCH_LIMIT,
        query_filter=query_filter,
    )

    if not hits:
        return RetrievalResult(query=query, mode=mode, raw_hits=[], chunks=[])

    hit_ids = [hit.id for hit in hits]
    points = client.retrieve(config.collection_alias, ids=hit_ids, with_vectors=True)
    dense_vector_by_id = {point.id: point.vector[DENSE_VECTOR_NAME] for point in points}
    query_dense_vector = embed_query(query)

    raw_hits = [
        RawHit(
            chunk_id=hit.payload["id"],
            score=hit.score,
            dense_score=_cosine_similarity(
                query_dense_vector, dense_vector_by_id.get(hit.id, [0.0] * len(query_dense_vector))
            ),
        )
        for hit in hits
    ]

    seen_texts: set[str] = set()
    chunks: list[RetrievedChunk] = []
    budget_used = 0
    for hit, raw in zip(hits, raw_hits):
        expanded_text = config.expand_fn(client, config.collection_alias, hit.payload)
        if expanded_text in seen_texts:
            continue  # another, higher- or equal-ranked hit already expanded to this same parent
        if chunks and budget_used + len(expanded_text) > MAX_CONTEXT_CHARS:
            continue  # keep checking lower-ranked hits — a later, shorter one might still fit
        seen_texts.add(expanded_text)
        chunks.append(
            RetrievedChunk(
                chunk_id=raw.chunk_id,
                score=raw.score,
                dense_score=raw.dense_score,
                text=expanded_text,
                payload=hit.payload,
            )
        )
        budget_used += len(expanded_text)

    return RetrievalResult(query=query, mode=mode, raw_hits=raw_hits, chunks=chunks)
