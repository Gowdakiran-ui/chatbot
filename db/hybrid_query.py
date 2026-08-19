"""Query-side hybrid dense+sparse retrieval (Piece 3) — fuses results with Qdrant's
built-in Reciprocal Rank Fusion via Prefetch + a FusionQuery, so this needs no separate
reranking service to get the benefit.

Only meaningful against a hybrid ("_v2"+) collection — a dense-only "_v1" collection has
no named sparse vector to prefetch from.
"""
from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, Fusion, FusionQuery, Prefetch, ScoredPoint

from db.config import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from db.embedding import embed_query
from db.sparse_embedding import embed_query_sparse


def hybrid_search(
    client: QdrantClient,
    collection: str,
    query_text: str,
    top_k: int = 5,
    prefetch_limit: int = 20,
    query_filter: Filter | None = None,
    dense_name: str = DENSE_VECTOR_NAME,
    sparse_name: str = SPARSE_VECTOR_NAME,
) -> list[ScoredPoint]:
    dense_vector = embed_query(query_text)
    sparse_vector = embed_query_sparse(query_text)

    return client.query_points(
        collection_name=collection,
        prefetch=[
            Prefetch(query=dense_vector, using=dense_name, limit=prefetch_limit, filter=query_filter),
            Prefetch(query=sparse_vector, using=sparse_name, limit=prefetch_limit, filter=query_filter),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
    ).points


def dense_only_search(
    client: QdrantClient,
    collection: str,
    query_text: str,
    top_k: int = 5,
    query_filter: Filter | None = None,
    dense_name: str = DENSE_VECTOR_NAME,
) -> list[ScoredPoint]:
    """Dense-only baseline against the same hybrid collection — used to A/B against
    hybrid_search() on the same "_v2" data (rather than against "_v1", which has a
    differently-shaped vector config)."""
    dense_vector = embed_query(query_text)
    return client.query_points(
        collection_name=collection,
        query=dense_vector,
        using=dense_name,
        query_filter=query_filter,
        limit=top_k,
    ).points
