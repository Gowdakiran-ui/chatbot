"""Integration tests for Piece 2's rate limiting wired into /chat — real FastAPI
app, real HTTP status codes, retrieval and generation both stubbed out so the
limiter itself is what's under test."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
from fastapi.testclient import TestClient

import serving.app as app_mod
from serving.auth import ClientIdentity
from serving.mode_config import Mode
from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter
from serving.retrieval import RawHit, RetrievalResult, RetrievedChunk


@pytest.fixture(autouse=True)
def _bypass_auth():
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: ClientIdentity(
        client_id="rl_test_client", label="Rate Limit Test Client"
    )
    yield
    app_mod.app.dependency_overrides.clear()


def _refusing_result() -> RetrievalResult:
    return RetrievalResult(query="x", mode=Mode.CHANAKYA, raw_hits=[], chunks=[])


def _passing_result() -> RetrievalResult:
    hit = RawHit(chunk_id="doc_a", score=0.9, dense_score=0.9)
    chunk = RetrievedChunk(chunk_id="doc_a", score=0.9, dense_score=0.9, text="context", payload={})
    return RetrievalResult(query="x", mode=Mode.CHANAKYA, raw_hits=[hit], chunks=[chunk])


def test_nth_plus_one_request_within_window_gets_429(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _refusing_result())
    limiter = InMemoryTokenBucketLimiter(max_requests=3, window_seconds=60)
    app_mod.app.dependency_overrides[app_mod.get_client_rate_limiter] = lambda: limiter
    client = TestClient(app_mod.app)

    for _ in range(3):
        r = client.post("/chat", json={"message": "hi", "mode": "chanakya"})
        assert r.status_code == 200

    r = client.post("/chat", json={"message": "hi", "mode": "chanakya"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_rate_limit_never_touches_retrieval_when_exceeded(monkeypatch):
    retrieve_spy = MagicMock(side_effect=lambda *a, **k: _refusing_result())
    monkeypatch.setattr(app_mod, "retrieve_context", retrieve_spy)
    limiter = InMemoryTokenBucketLimiter(max_requests=1, window_seconds=60)
    app_mod.app.dependency_overrides[app_mod.get_client_rate_limiter] = lambda: limiter
    client = TestClient(app_mod.app)

    client.post("/chat", json={"message": "hi", "mode": "chanakya"})
    assert retrieve_spy.call_count == 1

    client.post("/chat", json={"message": "hi", "mode": "chanakya"})  # this one should be rate-limited
    assert retrieve_spy.call_count == 1  # retrieval was never called for the limited request


def test_rate_limit_is_scoped_per_client_at_the_endpoint_level(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _refusing_result())
    limiter = InMemoryTokenBucketLimiter(max_requests=1, window_seconds=60)
    app_mod.app.dependency_overrides[app_mod.get_client_rate_limiter] = lambda: limiter

    identities = iter(
        [ClientIdentity(client_id="client_a", label="A"), ClientIdentity(client_id="client_b", label="B")]
    )
    app_mod.app.dependency_overrides[app_mod.get_current_client] = lambda: next(identities)
    client = TestClient(app_mod.app)

    r_a = client.post("/chat", json={"message": "hi", "mode": "chanakya"})
    assert r_a.status_code == 200  # client A's first request

    r_b = client.post("/chat", json={"message": "hi", "mode": "chanakya"})
    assert r_b.status_code == 200  # client B is a different bucket, unaffected by A


def test_generation_concurrency_cap_returns_429_before_streaming_starts(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result())
    fake_provider = MagicMock()
    fake_provider.generate.return_value = iter(["token"])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    app_mod.app.dependency_overrides[app_mod.get_generation_concurrency_limiter] = (
        lambda: GenerationConcurrencyLimiter(max_concurrent=0)  # no slots available at all
    )
    client = TestClient(app_mod.app)

    r = client.post("/chat", json={"message": "hi", "mode": "chanakya"})

    assert r.status_code == 429
    fake_provider.generate.assert_not_called()
