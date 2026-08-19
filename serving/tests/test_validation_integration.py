"""Integration tests for Piece 3's input validation + conversation ownership
wired into /chat — real FastAPI app, real HTTP status codes."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi.testclient import TestClient

import serving.app as app_mod
from serving.auth import ClientIdentity
from serving.config import MAX_MESSAGE_LENGTH
from serving.conversations import ConversationOwnershipStore
from serving.mode_config import Mode
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter
from serving.retrieval import RetrievalResult


@pytest.fixture(autouse=True)
def _bypass_limits(tmp_path):
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
    app_mod.app.dependency_overrides.pop(app_mod.get_client_rate_limiter, None)
    app_mod.app.dependency_overrides.pop(app_mod.get_generation_concurrency_limiter, None)
    app_mod.app.dependency_overrides.pop(app_mod.get_conversation_store, None)


@pytest.fixture
def client(monkeypatch):
    empty_result = RetrievalResult(query="x", mode=Mode.CHANAKYA, raw_hits=[], chunks=[])
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: empty_result)
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: MagicMock()
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: ClientIdentity(
        client_id="client_a", label="Client A"
    )
    yield TestClient(app_mod.app)
    app_mod.app.dependency_overrides.clear()


def test_oversized_message_rejected_with_422(client):
    response = client.post(
        "/chat",
        json={"message": "x" * (MAX_MESSAGE_LENGTH + 1), "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert response.status_code == 422


def test_empty_message_rejected_with_422(client):
    response = client.post(
        "/chat", json={"message": "", "mode": "chanakya"}, headers={"Authorization": "Bearer irrelevant"}
    )
    assert response.status_code == 422


def test_blank_whitespace_only_message_rejected_with_422(client):
    response = client.post(
        "/chat", json={"message": "   \n\t  ", "mode": "chanakya"}, headers={"Authorization": "Bearer irrelevant"}
    )
    assert response.status_code == 422


def test_message_with_control_characters_rejected_with_422(client):
    response = client.post(
        "/chat",
        json={"message": "hello\x00world", "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert response.status_code == 422


def test_message_at_max_length_is_accepted(client):
    response = client.post(
        "/chat",
        json={"message": "x" * MAX_MESSAGE_LENGTH, "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert response.status_code == 200


def test_message_with_normal_whitespace_is_accepted(client):
    response = client.post(
        "/chat",
        json={"message": "line one\nline two\ttabbed", "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert response.status_code == 200


def test_invalid_mode_value_rejected_cleanly_with_422_not_500(client):
    response = client.post(
        "/chat",
        json={"message": "hello", "mode": "not_a_real_mode"},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert response.status_code == 422


def test_missing_required_fields_rejected_with_422_not_500(client):
    response = client.post("/chat", json={"mode": "chanakya"}, headers={"Authorization": "Bearer irrelevant"})
    assert response.status_code == 422


# --- Conversation ownership -----------------------------------------------------------


def test_client_can_use_their_own_new_conversation_id(client):
    response = client.post(
        "/chat",
        json={"message": "hello", "mode": "chanakya", "conversation_id": "conv_owned_by_a"},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert response.status_code == 200


def test_client_can_continue_their_own_existing_conversation(client):
    conv_id = "conv_continued_by_a"
    first = client.post(
        "/chat",
        json={"message": "hello", "mode": "chanakya", "conversation_id": conv_id},
        headers={"Authorization": "Bearer irrelevant"},
    )
    second = client.post(
        "/chat",
        json={"message": "hello again", "mode": "chanakya", "conversation_id": conv_id},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert first.status_code == 200
    assert second.status_code == 200


def test_client_presenting_another_clients_conversation_id_gets_403(monkeypatch):
    empty_result = RetrievalResult(query="x", mode=Mode.CHANAKYA, raw_hits=[], chunks=[])
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: empty_result)
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: MagicMock()

    identities = iter([ClientIdentity(client_id="client_a", label="A"), ClientIdentity(client_id="client_b", label="B")])
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: next(identities)
    test_client = TestClient(app_mod.app)

    conv_id = "conv_owned_by_a_only"
    r_a = test_client.post(
        "/chat",
        json={"message": "hello", "mode": "chanakya", "conversation_id": conv_id},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert r_a.status_code == 200  # client A creates/owns it

    r_b = test_client.post(
        "/chat",
        json={"message": "hijack attempt", "mode": "chanakya", "conversation_id": conv_id},
        headers={"Authorization": "Bearer irrelevant"},
    )
    assert r_b.status_code == 403
    app_mod.app.dependency_overrides.clear()
