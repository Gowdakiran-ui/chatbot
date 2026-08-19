"""Tests for serving/retrieval.py — in-memory Qdrant, fake embedders (no model
load), mirroring preprocessing/tests/test_hybrid_query.py's fixtures."""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

import serving.retrieval as retrieval_mod
from db.parent_expansion import expand_chanakya_chunk
from db.version_bump import hybrid_build_fn
from serving.mode_config import Mode, ModeConfig

_NS = uuid.NAMESPACE_DNS


def _pid(chunk_id: str) -> str:
    return str(uuid.uuid5(_NS, chunk_id))


def _fake_dense(texts: list[str]) -> list[list[float]]:
    return [[len(t) % 7, len(t) % 5, 1.0, 0.5] for t in texts]


def _fake_sparse(texts: list[str]) -> list[SparseVector]:
    out = []
    for t in texts:
        tokens = sorted(set(t.lower().split()))
        indices = [abs(hash(tok)) % 100000 for tok in tokens]
        out.append(SparseVector(indices=indices, values=[1.0] * len(indices)))
    return out


@pytest.fixture
def client():
    return QdrantClient(":memory:")


def _build(client, tmp_path, rows) -> None:
    jsonl_path = tmp_path / "kb.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    build_fn = hybrid_build_fn(
        client,
        jsonl_path,
        embed_dense_fn=_fake_dense,
        embed_sparse_fn=_fake_sparse,
        id_fn=lambda row: _pid(row["id"]),
        payload_fn=lambda row: dict(row),
        vector_size=4,
    )
    build_fn("kb_test")


def _fake_config() -> ModeConfig:
    return ModeConfig(
        collection_alias="kb_test",
        system_prompt_path=Path("unused.md"),
        top_k=5,
        min_score=0.5,
        expand_fn=expand_chanakya_chunk,
        get_client=lambda: None,  # retrieve_context takes the client from config.get_client(); patched per-test below
        requires_disclaimer=False,
        max_tokens=800,
    )


@pytest.fixture(autouse=True)
def _patch_embedders(monkeypatch):
    monkeypatch.setattr(retrieval_mod, "embed_query", lambda text: _fake_dense([text])[0])
    import db.hybrid_query as hq

    monkeypatch.setattr(hq, "embed_query", lambda text: _fake_dense([text])[0])
    monkeypatch.setattr(hq, "embed_query_sparse", lambda text: _fake_sparse([text])[0])


def test_dedup_collapses_siblings_expanding_to_same_parent(tmp_path, client):
    rows = [
        {
            "id": f"arthashastra_book_ii_chapter_i_{i:03d}",
            "text": "leadership and treachery advice text",
            "source": "arthashastra",
            "chunk_type": "verse",
            "parent_id": "arthashastra_book_ii_chapter_i",
        }
        for i in range(1, 4)
    ]
    _build(client, tmp_path, rows)

    config = _fake_config()
    config = config.model_copy(update={"get_client": lambda: client, "top_k": 3})

    result = retrieval_mod.retrieve_context("leadership and treachery advice text", config, Mode.CHANAKYA)

    assert len(result.raw_hits) == 3  # all 3 siblings were real hits
    assert len(result.chunks) == 1  # but they all expand to the identical concatenated parent text
    assert result.chunks[0].text == "leadership and treachery advice text\n\nleadership and treachery advice text\n\nleadership and treachery advice text"


def test_budget_cap_drops_lower_ranked_chunks_that_dont_fit(tmp_path, client, monkeypatch):
    rows = [
        {"id": "doc_a", "text": "aaaa " * 200, "source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None},
        {"id": "doc_zzz_unrelated", "text": "bbbb " * 200, "source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None},
    ]
    _build(client, tmp_path, rows)
    monkeypatch.setattr(retrieval_mod, "MAX_CONTEXT_CHARS", 100)

    config = _fake_config()
    config = config.model_copy(update={"get_client": lambda: client, "top_k": 2})

    result = retrieval_mod.retrieve_context("aaaa", config, Mode.CHANAKYA)

    assert len(result.raw_hits) == 2
    assert len(result.chunks) == 1  # only the top-ranked hit fit under the tiny budget
    assert result.chunks[0].chunk_id == result.raw_hits[0].chunk_id


def test_dense_score_reflects_cosine_similarity_not_fused_rrf_score(tmp_path, client):
    rows = [{"id": "doc_a", "text": "alpha", "source": "corporate_chanakya", "chunk_type": "prose", "parent_id": None}]
    _build(client, tmp_path, rows)

    config = _fake_config()
    config = config.model_copy(update={"get_client": lambda: client, "top_k": 1})

    result = retrieval_mod.retrieve_context("alpha", config, Mode.CHANAKYA)

    # Query text "alpha" and doc text "alpha" produce identical fake dense vectors -> cosine similarity 1.0.
    assert result.raw_hits[0].dense_score == pytest.approx(1.0)
    assert result.top_dense_score == pytest.approx(1.0)


def test_no_hits_returns_empty_result_with_zeroed_top_scores(tmp_path, client):
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    _build(client, tmp_path, [{"id": "doc_a", "text": "alpha", "source": "x", "chunk_type": "prose", "parent_id": None}])
    # A filter matching no point forces an empty hit list without an invalid top_k.
    empty_filter = Filter(must=[FieldCondition(key="source", match=MatchValue(value="no_such_source"))])
    config = _fake_config()
    config = config.model_copy(update={"get_client": lambda: client, "top_k": 5})

    result = retrieval_mod.retrieve_context(
        "alpha", config, Mode.CHANAKYA, query_filter=empty_filter
    )

    assert result.raw_hits == []
    assert result.chunks == []
    assert result.top_score == 0.0
    assert result.top_dense_score == 0.0
