"""Tests for db/version_bump.hybrid_build_fn and db/hybrid_query — in-memory Qdrant,
fake embedders (no model load)."""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root, for `db.*`

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

from db.hybrid_query import dense_only_search, hybrid_search
from db.version_bump import hybrid_build_fn


@pytest.fixture
def client():
    return QdrantClient(":memory:")


def _fake_dense(texts: list[str]) -> list[list[float]]:
    # A trivial, deterministic "embedding": length-normalized character count in a
    # few buckets — good enough to give distinct, comparable vectors per test doc.
    return [[len(t) % 7, len(t) % 5, 1.0, 0.5] for t in texts]


def _fake_sparse_from_tokens(texts: list[str]) -> list[SparseVector]:
    # A trivial "BM25": one dimension per distinct lowercase word, present/absent.
    out = []
    for t in texts:
        tokens = sorted(set(t.lower().split()))
        indices = [abs(hash(tok)) % 100000 for tok in tokens]
        out.append(SparseVector(indices=indices, values=[1.0] * len(indices)))
    return out


def test_hybrid_build_fn_creates_dense_and_sparse_vectors(tmp_path, client):
    jsonl_path = tmp_path / "kb.jsonl"
    rows = [
        {"id": "doc_001", "text": "Nirav Modi fled India after the PNB fraud"},
        {"id": "doc_002", "text": "GDPR requires breach disclosure within 72 hours"},
        {"id": "doc_003", "text": "generic unrelated filler text about nothing exact"},
    ]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    build_fn = hybrid_build_fn(
        client,
        jsonl_path,
        embed_dense_fn=_fake_dense,
        embed_sparse_fn=_fake_sparse_from_tokens,
        id_fn=lambda row: str(uuid.uuid5(uuid.NAMESPACE_DNS, row["id"])),
        payload_fn=lambda row: dict(row),
        vector_size=4,
    )

    count = build_fn("kb_v2")
    assert count == 3

    info = client.get_collection("kb_v2")
    assert "dense" in info.config.params.vectors
    assert "sparse" in info.config.params.sparse_vectors

    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "doc_001"))
    point = client.retrieve("kb_v2", ids=[point_id], with_vectors=True)[0]
    assert "dense" in point.vector
    assert "sparse" in point.vector
    assert len(point.vector["dense"]) == 4
    assert len(point.vector["sparse"].indices) > 0


def test_hybrid_search_finds_exact_token_match_via_sparse(tmp_path, client, monkeypatch):
    jsonl_path = tmp_path / "kb.jsonl"
    rows = [
        {"id": "doc_pnb", "text": "Nirav Modi fled India after the PNB fraud"},
        {"id": "doc_gdpr", "text": "GDPR requires breach disclosure within 72 hours"},
        {"id": "doc_generic_1", "text": "some generic filler text about the weather"},
        {"id": "doc_generic_2", "text": "another generic filler text about traffic"},
    ]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    build_fn = hybrid_build_fn(
        client,
        jsonl_path,
        embed_dense_fn=_fake_dense,
        embed_sparse_fn=_fake_sparse_from_tokens,
        id_fn=lambda row: str(uuid.uuid5(uuid.NAMESPACE_DNS, row["id"])),
        payload_fn=lambda row: dict(row),
        vector_size=4,
    )
    build_fn("kb_v2")

    # Route hybrid_search's real embedders through our fakes for this test.
    import db.hybrid_query as hq

    monkeypatch.setattr(hq, "embed_query", lambda text: _fake_dense([text])[0])
    monkeypatch.setattr(hq, "embed_query_sparse", lambda text: _fake_sparse_from_tokens([text])[0])

    results = hybrid_search(client, "kb_v2", "Nirav Modi PNB fraud", top_k=2)
    top_ids = [r.payload["id"] for r in results]
    assert "doc_pnb" in top_ids


def test_dense_only_search_ignores_sparse_vector(tmp_path, client, monkeypatch):
    jsonl_path = tmp_path / "kb.jsonl"
    rows = [{"id": "doc_a", "text": "alpha"}, {"id": "doc_b", "text": "beta beta beta"}]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    build_fn = hybrid_build_fn(
        client,
        jsonl_path,
        embed_dense_fn=_fake_dense,
        embed_sparse_fn=_fake_sparse_from_tokens,
        id_fn=lambda row: str(uuid.uuid5(uuid.NAMESPACE_DNS, row["id"])),
        payload_fn=lambda row: dict(row),
        vector_size=4,
    )
    build_fn("kb_v2")

    import db.hybrid_query as hq

    monkeypatch.setattr(hq, "embed_query", lambda text: _fake_dense([text])[0])

    results = dense_only_search(client, "kb_v2", "alpha", top_k=2)
    assert len(results) == 2
