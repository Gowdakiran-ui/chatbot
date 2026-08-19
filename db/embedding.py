"""Local, CPU-only embedding model for the Chanakya KB.

Deliberately lightweight for a weak laptop (no GPU, 16GB RAM): `nomic-embed-text-v1.5`
is a ~137M-param model, runs comfortably on CPU. No API key, no network call except the
one-time model download from HuggingFace on first use (then fully offline/cached).

nomic-embed-text-v1.5 is instruction-prefixed: document text and search queries need
different prefixes for retrieval to work well. Get this backwards and retrieval quality
drops — see DOCUMENT_PREFIX / QUERY_PREFIX below.
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from db.config import DOCUMENT_PREFIX, EMBED_BATCH_SIZE, MODEL_NAME, QUERY_PREFIX, VECTOR_SIZE

# Re-exported for backward compatibility — existing code imports these names from here.
__all__ = [
    "MODEL_NAME",
    "VECTOR_SIZE",
    "DOCUMENT_PREFIX",
    "QUERY_PREFIX",
    "get_model",
    "embed_documents",
    "embed_query",
]

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazily loads and caches the embedding model (loading takes a few seconds once
    the weights are cached locally; several minutes the very first time)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
    return _model


def embed_documents(texts: list[str], batch_size: int = EMBED_BATCH_SIZE) -> list[list[float]]:
    """Embeds chunk text for storage. Applies DOCUMENT_PREFIX; normalizes vectors so
    Cosine distance in Qdrant behaves correctly."""
    model = get_model()
    prefixed = [DOCUMENT_PREFIX + t for t in texts]
    vectors = model.encode(
        prefixed,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """Embeds a single user query for retrieval. Applies QUERY_PREFIX (not
    DOCUMENT_PREFIX) — this is the retrieval-time counterpart to embed_documents()."""
    model = get_model()
    vector = model.encode(
        [QUERY_PREFIX + text],
        normalize_embeddings=True,
    )
    return vector[0].tolist()
