"""Tests for serving/floor.py — the refusal path. Two layers: deterministic unit
tests on the floor-check functions with a hand-built RetrievalResult (precise
control over scores), and one real-retrieval integration test with a query
engineered to produce a low dense score, matching task.md's Piece 4 requirement."""
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

import serving.retrieval as retrieval_mod
from db.parent_expansion import expand_chanakya_chunk
from db.version_bump import hybrid_build_fn
from serving.floor import answer_with_floor, check_floor, passes_floor, refusal_text_for
from serving.mode_config import Mode, ModeConfig
from serving.retrieval import RawHit, RetrievalResult, RetrievedChunk, retrieve_context

_NS = uuid.NAMESPACE_DNS


def _pid(chunk_id: str) -> str:
    return str(uuid.uuid5(_NS, chunk_id))


def _fake_config(min_score: float = 0.6) -> ModeConfig:
    return ModeConfig(
        collection_alias="kb_test",
        system_prompt_path=Path("unused.md"),
        top_k=5,
        min_score=min_score,
        expand_fn=expand_chanakya_chunk,
        get_client=lambda: None,
        requires_disclaimer=False,
        max_tokens=800,
    )


def _result(top_dense_score: float, top_score: float = 0.5) -> RetrievalResult:
    hit = RawHit(chunk_id="doc_a", score=top_score, dense_score=top_dense_score)
    chunk = RetrievedChunk(chunk_id="doc_a", score=top_score, dense_score=top_dense_score, text="some text", payload={})
    return RetrievalResult(query="a test query", mode=Mode.CHANAKYA, raw_hits=[hit], chunks=[chunk])


# --- Deterministic unit tests -------------------------------------------------------


def test_passes_floor_true_when_dense_score_at_or_above_min():
    config = _fake_config(min_score=0.6)
    assert passes_floor(_result(top_dense_score=0.6), config) is True
    assert passes_floor(_result(top_dense_score=0.9), config) is True


def test_passes_floor_false_when_dense_score_below_min():
    config = _fake_config(min_score=0.6)
    assert passes_floor(_result(top_dense_score=0.59), config) is False


def test_check_floor_uses_dense_score_not_fused_score():
    # Fused score is high (0.9) but dense score is low — floor must key off dense_score.
    config = _fake_config(min_score=0.6)
    result = _result(top_dense_score=0.1, top_score=0.9)
    check = check_floor(result, config)
    assert check.passed is False
    assert check.refusal_text is not None


def test_check_floor_pass_has_no_refusal_text():
    config = _fake_config(min_score=0.6)
    check = check_floor(_result(top_dense_score=0.95), config)
    assert check.passed is True
    assert check.refusal_text is None


def test_refusal_text_differs_per_mode_and_crisis_has_disclaimer():
    chanakya_text = refusal_text_for(Mode.CHANAKYA)
    crisis_text = refusal_text_for(Mode.CRISIS)
    assert chanakya_text != crisis_text
    assert "This is not legal advice." in crisis_text


def test_answer_with_floor_refuses_without_calling_generate_fn(monkeypatch):
    config = _fake_config(min_score=0.6)
    low_result = _result(top_dense_score=0.1)
    monkeypatch.setattr(retrieval_mod, "retrieve_context", lambda *a, **k: low_result)
    monkeypatch.setattr("serving.floor.retrieve_context", lambda *a, **k: low_result)

    generate_fn = MagicMock()
    answer = answer_with_floor("irrelevant query", config, Mode.CHANAKYA, generate_fn)

    generate_fn.assert_not_called()
    assert answer == refusal_text_for(Mode.CHANAKYA)


def test_answer_with_floor_generates_when_floor_passes(monkeypatch):
    config = _fake_config(min_score=0.6)
    high_result = _result(top_dense_score=0.95)
    monkeypatch.setattr("serving.floor.retrieve_context", lambda *a, **k: high_result)

    generate_fn = MagicMock(return_value="a grounded answer")
    answer = answer_with_floor("a relevant query", config, Mode.CHANAKYA, generate_fn)

    generate_fn.assert_called_once_with(high_result)
    assert answer == "a grounded answer"


# --- Real-retrieval integration test ------------------------------------------------


def _fake_dense(texts: list[str]) -> list[list[float]]:
    return [[len(t) % 7, len(t) % 5, 1.0, 0.5] for t in texts]


def _fake_sparse(texts: list[str]) -> list[SparseVector]:
    out = []
    for t in texts:
        tokens = sorted(set(t.lower().split()))
        indices = [abs(hash(tok)) % 100000 for tok in tokens]
        out.append(SparseVector(indices=indices, values=[1.0] * len(indices)))
    return out


@pytest.fixture(autouse=True)
def _patch_embedders(monkeypatch):
    monkeypatch.setattr(retrieval_mod, "embed_query", lambda text: _fake_dense([text])[0])
    import db.hybrid_query as hq

    monkeypatch.setattr(hq, "embed_query", lambda text: _fake_dense([text])[0])
    monkeypatch.setattr(hq, "embed_query_sparse", lambda text: _fake_sparse([text])[0])


def test_engineered_low_score_query_triggers_refusal_without_llm_call(tmp_path):
    """Task-specified test: a query engineered to return only low-score/irrelevant
    hits must trigger the refusal path, and the (mocked) LLM must see zero calls."""
    client = QdrantClient(":memory:")
    jsonl_path = tmp_path / "kb.jsonl"
    # doc text length 5 -> fake dense vector [5, 0, 1, 0.5]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "doc_a", "text": "alpha", "source": "x", "chunk_type": "prose", "parent_id": None}) + "\n")

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

    # Query text engineered to length 21 -> fake dense vector [0, 1, 1, 0.5], cosine
    # similarity to the doc's [5, 0, 1, 0.5] is ~0.16 — well under any real min_score.
    query = "z" * 21
    config = _fake_config(min_score=0.6)
    config = config.model_copy(update={"get_client": lambda: client})

    result = retrieve_context(query, config, Mode.CHANAKYA)
    assert result.top_dense_score < 0.3  # confirm the query really is engineered low, not a fluke

    generate_fn = MagicMock()
    check = check_floor(result, config)
    answer = check.refusal_text if not check.passed else generate_fn(result)

    generate_fn.assert_not_called()
    assert check.passed is False
    assert answer == refusal_text_for(Mode.CHANAKYA)
