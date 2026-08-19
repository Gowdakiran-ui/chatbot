"""End-to-end verification for Piece 1: scripts/issue_token.py issues a real
token against a real (temp) SQLite DB, that token is used in a real /chat request
and gets a 200, and a tampered version of that same token gets a 401 — the exact
check task.md asks for by name."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi.testclient import TestClient

import serving.app as app_mod
from scripts.issue_token import issue_token
from serving.conversations import ConversationOwnershipStore
from serving.retrieval import RetrievalResult
from serving.mode_config import Mode
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter


@pytest.fixture
def isolated_auth_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth_test.db"
    monkeypatch.setattr("serving.auth.DB_PATH", db_path)
    return db_path


@pytest.fixture
def client_app(monkeypatch, isolated_auth_db, tmp_path):
    # Stub retrieval entirely (no Qdrant call, no network) with a zero-score
    # result, so the floor always refuses — the point of this test is proving
    # the auth layer end to end, not retrieval or generation.
    empty_result = RetrievalResult(query="x", mode=Mode.CHANAKYA, raw_hits=[], chunks=[])
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: empty_result)
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: MagicMock()
    # This suite is about auth (Piece 1), not rate limiting/ownership (Piece 2/3)
    # — give it fresh, effectively-unlimited/no-op instances so it can't be
    # affected by other tests' state in the same session.
    app_mod.app.dependency_overrides[app_mod.get_client_rate_limiter] = lambda: InMemoryTokenBucketLimiter(
        max_requests=10_000, window_seconds=60
    )
    app_mod.app.dependency_overrides[app_mod.get_generation_concurrency_limiter] = (
        lambda: GenerationConcurrencyLimiter(max_concurrent=10_000)
    )
    app_mod.app.dependency_overrides[app_mod.get_conversation_store] = lambda: ConversationOwnershipStore(
        db_path=tmp_path / "conversations_test.db"
    )
    yield TestClient(app_mod.app)
    app_mod.app.dependency_overrides.clear()


def test_issued_token_used_in_real_request_gets_200(client_app, isolated_auth_db):
    token = issue_token("e2e_client", "E2E Test Client")

    response = client_app.post(
        "/chat",
        json={"message": "irrelevant, floor always refuses in this test", "mode": "chanakya"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_tampered_token_gets_401(client_app, isolated_auth_db):
    token = issue_token("e2e_client_2", "E2E Test Client 2")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    response = client_app.post(
        "/chat",
        json={"message": "irrelevant", "mode": "chanakya"},
        headers={"Authorization": f"Bearer {tampered}"},
    )

    assert response.status_code == 401


def test_missing_token_gets_401(client_app):
    response = client_app.post("/chat", json={"message": "irrelevant", "mode": "chanakya"})

    assert response.status_code == 401


# --- AUTH_DISABLED (team-review-prep task, 2026-08-19) -------------------------------


def test_auth_disabled_true_allows_request_with_no_authorization_header_at_all(client_app, monkeypatch):
    monkeypatch.setattr("serving.auth.AUTH_DISABLED", True)

    response = client_app.post("/chat", json={"message": "irrelevant", "mode": "chanakya"})

    assert response.status_code == 200
