"""Tests for the POST /chat endpoint (Piece 6) — in-memory Qdrant for retrieval,
a fake GenerationProvider for generation, real FastAPI TestClient. Wires the whole
resolve-mode -> retrieve+expand -> floor -> prompt -> generate -> stream path."""
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

import serving.app as app_mod
import serving.retrieval as retrieval_mod
from db.parent_expansion import expand_chanakya_chunk, expand_crisis_chunk
from db.version_bump import hybrid_build_fn
from serving.auth import ClientIdentity
from serving.conversations import ConversationOwnershipStore
from serving.disclaimer import NOT_LEGAL_ADVICE_LINE
from serving.mode_config import MODE_CONFIG, Mode, ModeConfig
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter

_NS = uuid.NAMESPACE_DNS


@pytest.fixture(autouse=True)
def _bypass_auth_and_limits(tmp_path):
    """These tests exercise retrieval/floor/generation wiring, not auth, rate
    limiting, or conversation ownership (covered in their own test files) —
    override get_current_client with a fixed identity, give each test a fresh,
    effectively-unlimited rate limiter/concurrency cap, and a conversation store
    backed by a throwaway temp DB, so the module-level singletons in serving.app
    (shared across the whole test session) can't cause one test's requests to
    spuriously 429/403 another's, and tests don't write into the real project DB."""
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: ClientIdentity(
        client_id="test_client", label="Test Client"
    )
    app_mod.app.dependency_overrides[app_mod.get_client_rate_limiter] = lambda: InMemoryTokenBucketLimiter(
        max_requests=10_000, window_seconds=60
    )
    app_mod.app.dependency_overrides[app_mod.get_generation_concurrency_limiter] = (
        lambda: GenerationConcurrencyLimiter(max_concurrent=10_000)
    )
    app_mod.app.dependency_overrides[app_mod.get_conversation_store] = lambda: ConversationOwnershipStore(
        db_path=tmp_path / "conversations_test.db"
    )
    yield
    app_mod.app.dependency_overrides.pop(app_mod.get_current_client, None)
    app_mod.app.dependency_overrides.pop(app_mod.get_client_rate_limiter, None)
    app_mod.app.dependency_overrides.pop(app_mod.get_generation_concurrency_limiter, None)
    app_mod.app.dependency_overrides.pop(app_mod.get_conversation_store, None)


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


@pytest.fixture(autouse=True)
def _patch_embedders(monkeypatch):
    monkeypatch.setattr(retrieval_mod, "embed_query", lambda text: _fake_dense([text])[0])
    import db.hybrid_query as hq

    monkeypatch.setattr(hq, "embed_query", lambda text: _fake_dense([text])[0])
    monkeypatch.setattr(hq, "embed_query_sparse", lambda text: _fake_sparse([text])[0])


def _build_collection(tmp_path, rows) -> QdrantClient:
    client = QdrantClient(":memory:")
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
    return client


def _fake_config(client, expand_fn, min_score, requires_disclaimer) -> ModeConfig:
    return ModeConfig(
        collection_alias="kb_test",
        system_prompt_path=Path(__file__).with_name("_fake_system.md"),
        top_k=5,
        min_score=min_score,
        expand_fn=expand_fn,
        get_client=lambda: client,
        requires_disclaimer=requires_disclaimer,
        max_tokens=800,
    )


@pytest.fixture
def fake_system_prompt(tmp_path_factory):
    path = tmp_path_factory.mktemp("prompts") / "_fake_system.md"
    path.write_text("You are a test assistant.", encoding="utf-8")
    return path


def _install_mode_config(monkeypatch, mode: Mode, config: ModeConfig, fake_system_prompt: Path):
    config = config.model_copy(update={"system_prompt_path": fake_system_prompt})
    monkeypatch.setitem(app_mod.MODE_CONFIG, mode, config)
    return config


def _parse_sse_events(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        assert block.startswith("data: ")
        events.append(json.loads(block[len("data: ") :]))
    return events


@pytest.fixture
def client_app():
    return TestClient(app_mod.app)


def test_chat_refusal_path_never_calls_generation_provider(tmp_path, monkeypatch, client_app, fake_system_prompt):
    rows = [{"id": "doc_a", "text": "alpha", "source": "x", "chunk_type": "prose", "parent_id": None}]
    qdrant = _build_collection(tmp_path, rows)
    config = _fake_config(qdrant, expand_chanakya_chunk, min_score=0.9, requires_disclaimer=False)
    _install_mode_config(monkeypatch, Mode.CHANAKYA, config, fake_system_prompt)

    fake_provider = MagicMock()
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider

    # "z"*21 -> fake dense vector [0,1,1,0.5], far from "alpha"'s [5,0,1,0.5]
    # (cosine ~0.16) -> reliably below the 0.9 floor, unlike an exact-text match.
    response = client_app.post("/chat", json={"message": "z" * 21, "mode": "chanakya"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(response.text)
    assert events[0]["type"] == "token"
    assert events[-1] == {
        "type": "final",
        "mode": "chanakya",
        "refused": True,
        "top_score": events[-1]["top_score"],
        "top_dense_score": events[-1]["top_dense_score"],
        "cited_chunk_ids": [],
        "conversation_id": None,
    }
    fake_provider.generate.assert_not_called()
    app_mod.app.dependency_overrides.clear()


def test_chat_generation_path_streams_tokens_and_cites_sources(tmp_path, monkeypatch, client_app, fake_system_prompt):
    rows = [{"id": "doc_a", "text": "alpha", "source": "x", "chunk_type": "prose", "parent_id": None}]
    qdrant = _build_collection(tmp_path, rows)
    config = _fake_config(qdrant, expand_chanakya_chunk, min_score=0.5, requires_disclaimer=False)
    _install_mode_config(monkeypatch, Mode.CHANAKYA, config, fake_system_prompt)

    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["Hello", " world"])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider

    response = client_app.post("/chat", json={"message": "alpha", "mode": "chanakya", "conversation_id": "abc"})

    events = _parse_sse_events(response.text)
    token_events = [e for e in events if e["type"] == "token"]
    final_event = events[-1]

    assert [e["text"] for e in token_events] == ["Hello", " world"]
    assert final_event["type"] == "final"
    assert final_event["refused"] is False
    assert final_event["cited_chunk_ids"] == ["doc_a"]
    assert final_event["conversation_id"] == "abc"
    fake_provider.generate.assert_called_once()
    app_mod.app.dependency_overrides.clear()


def test_chat_crisis_appends_disclaimer_when_model_omits_it(tmp_path, monkeypatch, client_app, fake_system_prompt):
    rows = [{"id": "case_001_summary", "text": "a case summary", "case_id": "case_001", "chunk_type": "summary"}]
    qdrant = _build_collection(tmp_path, rows)
    config = _fake_config(qdrant, expand_crisis_chunk, min_score=0.5, requires_disclaimer=True)
    _install_mode_config(monkeypatch, Mode.CRISIS, config, fake_system_prompt)

    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["Here is grounded advice with no disclaimer."])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider

    response = client_app.post("/chat", json={"message": "a case summary", "mode": "crisis"})

    events = _parse_sse_events(response.text)
    full_text = "".join(e["text"] for e in events if e["type"] == "token")

    assert NOT_LEGAL_ADVICE_LINE in full_text
    app_mod.app.dependency_overrides.clear()


def test_chat_crisis_does_not_duplicate_disclaimer_when_model_already_includes_it(
    tmp_path, monkeypatch, client_app, fake_system_prompt
):
    rows = [{"id": "case_001_summary", "text": "a case summary", "case_id": "case_001", "chunk_type": "summary"}]
    qdrant = _build_collection(tmp_path, rows)
    config = _fake_config(qdrant, expand_crisis_chunk, min_score=0.5, requires_disclaimer=True)
    _install_mode_config(monkeypatch, Mode.CRISIS, config, fake_system_prompt)

    model_output = f"Grounded advice. {NOT_LEGAL_ADVICE_LINE}"
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter([model_output])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider

    response = client_app.post("/chat", json={"message": "a case summary", "mode": "crisis"})

    events = _parse_sse_events(response.text)
    token_events = [e for e in events if e["type"] == "token"]

    assert len(token_events) == 1  # no extra disclaimer token appended
    assert token_events[0]["text"] == model_output
    app_mod.app.dependency_overrides.clear()


def test_chat_generation_error_yields_error_event(tmp_path, monkeypatch, client_app, fake_system_prompt):
    rows = [{"id": "doc_a", "text": "alpha", "source": "x", "chunk_type": "prose", "parent_id": None}]
    qdrant = _build_collection(tmp_path, rows)
    config = _fake_config(qdrant, expand_chanakya_chunk, min_score=0.5, requires_disclaimer=False)
    _install_mode_config(monkeypatch, Mode.CHANAKYA, config, fake_system_prompt)

    def _raise():
        raise RuntimeError("upstream provider exploded")
        yield  # pragma: no cover - unreachable, makes this a generator

    fake_provider = MagicMock()
    fake_provider.generate.return_value = _raise()
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider

    response = client_app.post("/chat", json={"message": "alpha", "mode": "chanakya"})

    events = _parse_sse_events(response.text)
    assert events[-1]["type"] == "error"
    assert "upstream provider exploded" in events[-1]["message"]
    assert not any(e["type"] == "final" for e in events)  # no fabricated success payload
    app_mod.app.dependency_overrides.clear()
