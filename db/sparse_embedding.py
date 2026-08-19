"""Local sparse (BM25) embedding — the counterpart to db/embedding.py's dense
nomic-embed-text-v1.5 vectors, for hybrid retrieval (Piece 3 of the hardening task).

Uses fastembed's `Qdrant/bm25` — pure term statistics, no neural model, no GPU. Like the
dense embedder, document text and queries go through different fastembed calls
(`embed` vs `query_embed`) — this is BM25's own doc/query asymmetry, the same shape as
nomic's DOCUMENT_PREFIX/QUERY_PREFIX split, just enforced by fastembed itself rather
than a prefix string.
"""
from __future__ import annotations

from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

from db.config import SPARSE_MODEL_NAME

_model: SparseTextEmbedding | None = None


def get_model() -> SparseTextEmbedding:
    global _model
    if _model is None:
        _model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    return _model


def embed_documents_sparse(texts: list[str]) -> list[SparseVector]:
    model = get_model()
    return [SparseVector(indices=e.indices.tolist(), values=e.values.tolist()) for e in model.embed(texts)]


def embed_query_sparse(text: str) -> SparseVector:
    model = get_model()
    (e,) = model.query_embed([text])
    return SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
