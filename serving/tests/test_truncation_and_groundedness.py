"""Integration tests for the generation-quality fixes: truncation detection via
finish_reason (Fix 1) and the soft groundedness check (Fix 2), both wired into
the real /chat endpoint."""
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi.testclient import TestClient

import serving.app as app_mod
from serving.auth import ClientIdentity
from serving.conversations import ConversationOwnershipStore
from serving.mode_config import Mode
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter
from serving.retrieval import RawHit, RetrievalResult, RetrievedChunk


@pytest.fixture(autouse=True)
def _bypass(tmp_path):
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: ClientIdentity(
        client_id="tg_test_client", label="Truncation/Groundedness Test Client"
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
    app_mod.app.dependency_overrides.clear()


def _passing_result(mode: Mode, text: str = "grounded context") -> RetrievalResult:
    hit = RawHit(chunk_id="doc_a", score=0.9, dense_score=0.9)
    chunk = RetrievedChunk(chunk_id="doc_a", score=0.9, dense_score=0.9, text=text, payload={})
    return RetrievalResult(query="x", mode=mode, raw_hits=[hit], chunks=[chunk])


def _parse_sse(text: str) -> list[dict]:
    import json

    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            events.append(json.loads(block[len("data: ") :]))
    return events


# --- Fix 1: truncation detection ------------------------------------------------------


def test_crisis_mode_passes_1400_max_tokens_to_provider(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CRISIS))
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["a full answer"])
    fake_provider.last_finish_reason = "stop"
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    client.post("/chat", json={"message": "hi", "mode": "crisis"}, headers={"Authorization": "Bearer x"})

    _, kwargs = fake_provider.generate.call_args
    assert kwargs["max_tokens"] == 1400


def test_chanakya_mode_passes_800_max_tokens_to_provider(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CHANAKYA))
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["a full answer"])
    fake_provider.last_finish_reason = "stop"
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    client.post("/chat", json={"message": "hi", "mode": "chanakya"}, headers={"Authorization": "Bearer x"})

    _, kwargs = fake_provider.generate.call_args
    assert kwargs["max_tokens"] == 800


def test_truncated_response_gets_notice_and_forced_disclaimer(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CRISIS))
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["The CEO"])  # cut off mid-sentence, no disclaimer
    fake_provider.last_finish_reason = "length"
    fake_provider.usage_log = [{"input_tokens": 100, "output_tokens": 1400}]
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    response = client.post(
        "/chat", json={"message": "hi", "mode": "crisis"}, headers={"Authorization": "Bearer x"}
    )

    events = _parse_sse(response.text)
    tokens = [e["text"] for e in events if e["type"] == "token"]
    full_text = "".join(tokens)

    assert app_mod.TRUNCATION_NOTICE in full_text
    assert "This is not legal advice." in full_text
    # order: model output, then truncation notice, then disclaimer
    assert full_text.index(app_mod.TRUNCATION_NOTICE) < full_text.index("This is not legal advice.")


def test_non_truncated_response_gets_no_truncation_notice(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CHANAKYA))
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["a complete, finished answer."])
    fake_provider.last_finish_reason = "stop"
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    response = client.post(
        "/chat", json={"message": "hi", "mode": "chanakya"}, headers={"Authorization": "Bearer x"}
    )

    events = _parse_sse(response.text)
    full_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert app_mod.TRUNCATION_NOTICE not in full_text


def test_truncation_is_logged_with_mode_query_and_token_count(monkeypatch, caplog):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CRISIS))
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["cut off"])
    fake_provider.last_finish_reason = "length"
    fake_provider.usage_log = [{"input_tokens": 50, "output_tokens": 1400}]
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    with caplog.at_level(logging.WARNING, logger="serving.app"):
        client.post(
            "/chat", json={"message": "a truncation-triggering query", "mode": "crisis"},
            headers={"Authorization": "Bearer x"},
        )

    records = [r.message for r in caplog.records if "generation_truncated" in r.message]
    assert len(records) == 1
    assert "a truncation-triggering query" in records[0]
    assert "output_tokens=1400" in records[0]
    assert "max_tokens=1400" in records[0]


# --- Fix 2: groundedness check ---------------------------------------------------------


def test_ungrounded_embellishment_is_flagged_and_logged(monkeypatch, caplog):
    context_text = "Mr Chheda gave the businessman a cheque to rebuild his company."
    monkeypatch.setattr(
        app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CHANAKYA, text=context_text)
    )
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(
        ["This is the conduct of a *rajarshi*, drawing on the *Arthashastra*."]
    )
    fake_provider.last_finish_reason = "stop"
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    with caplog.at_level(logging.INFO, logger="serving.app"):
        response = client.post(
            "/chat", json={"message": "the Chheda story", "mode": "chanakya"},
            headers={"Authorization": "Bearer x"},
        )

    assert response.status_code == 200  # detection only — response still delivered normally
    records = [r.message for r in caplog.records if r.message.startswith("groundedness_flagged")]
    assert len(records) == 1
    assert "rajarshi" in records[0].lower()

    turn_records = [r.message for r in caplog.records if "chat_turn" in r.message]
    assert "groundedness_flagged=True" in turn_records[0]


def test_grounded_answer_is_not_flagged(monkeypatch, caplog):
    context_text = (
        "Company: Punjab National Bank case record. Year: 2018. Mehul Choksi was arrested in Belgium in 2025."
    )
    monkeypatch.setattr(
        app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CRISIS, text=context_text)
    )
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(
        ["Mehul Choksi was arrested in Belgium in 2025, per the Punjab National Bank case record."]
    )
    fake_provider.last_finish_reason = "stop"
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    with caplog.at_level(logging.WARNING, logger="serving.app"):
        client.post(
            "/chat", json={"message": "PNB case", "mode": "crisis"}, headers={"Authorization": "Bearer x"}
        )

    assert not any("groundedness_flagged" in r.message for r in caplog.records if r.levelno == logging.WARNING)
