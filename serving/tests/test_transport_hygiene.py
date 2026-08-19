"""Integration tests for Piece 5: secrets never reach a client-facing error
response, CORS is an explicit allowlist (never "*"), and an oversized request
body is rejected at the ASGI level before Pydantic validation ever runs."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import serving.app as app_mod
from serving.auth import ClientIdentity
from serving.config import ALLOWED_ORIGINS, MAX_BODY_BYTES, MAX_MESSAGE_LENGTH
from serving.conversations import ConversationOwnershipStore
from serving.mode_config import Mode
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter
from serving.retrieval import RawHit, RetrievalResult, RetrievedChunk


@pytest.fixture(autouse=True)
def _bypass(tmp_path):
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: ClientIdentity(
        client_id="hygiene_test_client", label="Hygiene Test Client"
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


def _passing_result() -> RetrievalResult:
    hit = RawHit(chunk_id="doc_a", score=0.9, dense_score=0.9)
    chunk = RetrievedChunk(chunk_id="doc_a", score=0.9, dense_score=0.9, text="grounded context", payload={})
    return RetrievalResult(query="x", mode=Mode.CHANAKYA, raw_hits=[hit], chunks=[chunk])


# --- Secrets never reach the client (or a log line) ----------------------------------


def test_generation_error_never_leaks_the_api_key_to_the_client(monkeypatch, caplog):
    """Deliberately triggers a generation error whose message contains the real
    configured secret (simulating a worst-case bug elsewhere that embeds it) and
    confirms the raw key is not present anywhere in the response body."""
    secret_value = "sk-or-real-secret-should-never-leak-98765"
    monkeypatch.setenv("openrouter_api_key", secret_value)
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result())

    def _raise():
        raise RuntimeError(f"OpenRouter call failed: unauthorized (key={secret_value})")
        yield  # pragma: no cover - unreachable, makes this a generator

    fake_provider = MagicMock()
    fake_provider.generate.return_value = _raise()
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    response = client.post(
        "/chat",
        json={"message": "hello", "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )

    assert secret_value not in response.text
    assert not any(secret_value in record.message for record in caplog.records)


# --- CORS: explicit allowlist, never "*" ----------------------------------------------


def test_allowed_origins_config_is_never_wildcard():
    assert "*" not in ALLOWED_ORIGINS


def test_cors_allows_configured_origin_and_rejects_others():
    # Build an isolated app using the exact same middleware wiring pattern as
    # serving/app.py, with a specific allowlist — verifies the mechanism itself
    # rather than depending on whatever ALLOWED_ORIGINS happens to be in this
    # environment's .env.
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://app.onlyne.example"],
        allow_credentials=True,
        allow_methods=["POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @test_app.post("/chat")
    def _stub():
        return {"ok": True}

    client = TestClient(test_app)

    allowed = client.post("/chat", headers={"Origin": "https://app.onlyne.example"})
    assert allowed.headers.get("access-control-allow-origin") == "https://app.onlyne.example"

    disallowed = client.post("/chat", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in disallowed.headers


# --- Request body size limit (ASGI level) ---------------------------------------------


def test_oversized_body_rejected_with_413_before_validation(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result())
    client = TestClient(app_mod.app)

    # Far larger than MAX_BODY_BYTES, and also larger than MAX_MESSAGE_LENGTH --
    # 413 (not 422) proves the ASGI-level cap caught it first, as a distinct layer.
    huge_message = "x" * (MAX_BODY_BYTES * 2)
    response = client.post(
        "/chat",
        json={"message": huge_message, "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )

    assert response.status_code == 413


def test_normal_sized_body_is_unaffected_by_the_limit(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result())
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["ok"])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    response = client.post(
        "/chat",
        json={"message": "a perfectly normal chat message", "mode": "chanakya"},
        headers={"Authorization": "Bearer irrelevant"},
    )

    assert response.status_code == 200
