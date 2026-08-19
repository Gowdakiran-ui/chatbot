"""Empty-response investigation (2026-08-18), Piece 3 fix: a bounded single
auto-retry when provider.generate() returns effectively empty content with
finish_reason != "length" — diagnosed as occasional degenerate completions
from OpenRouter's backend routing, not an application bug (see the task
report for the live-log evidence: reasoning confirmed disabled on every real
call site, single call site confirmed, truncation ruled out via finish_reason,
4/4 live reproduction attempts came back with full content)."""
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
        client_id="empty_retry_test_client", label="Empty-Response Retry Test Client"
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


def _passing_result(mode: Mode) -> RetrievalResult:
    hit = RawHit(chunk_id="doc_a", score=0.9, dense_score=0.9)
    chunk = RetrievedChunk(chunk_id="doc_a", score=0.9, dense_score=0.9, text="grounded context", payload={})
    return RetrievalResult(query="x", mode=mode, raw_hits=[hit], chunks=[chunk])


def _parse_sse(text: str) -> list[dict]:
    import json

    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if block:
            events.append(json.loads(block[len("data: ") :]))
    return events


class _StatefulProvider:
    """A fake provider whose generate() call returns a different
    (tokens, finish_reason) pair on each successive call — MagicMock's
    return_value can't do this since the same exhausted iterator would be
    returned on a second call, which would make a real retry silently look
    empty regardless of what the test intends."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.call_count = 0
        self.last_finish_reason = None
        self.usage_log = []

    def generate(self, prompt, system, stream=True, max_tokens=None):
        tokens, finish_reason = self._responses[self.call_count]
        self.call_count += 1
        self.last_finish_reason = finish_reason
        self.usage_log.append({"input_tokens": 10, "output_tokens": len(tokens)})
        return iter(tokens)


def test_empty_response_triggers_single_retry_and_uses_retry_content(monkeypatch, caplog):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CHANAKYA))
    fake_provider = _StatefulProvider(
        [
            ([], "stop"),  # degenerate empty completion
            (["A real, grounded ", "answer this time."], "stop"),  # retry succeeds
        ]
    )
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    with caplog.at_level(logging.WARNING, logger="serving.app"):
        response = client.post(
            "/chat", json={"message": "hi", "mode": "chanakya"}, headers={"Authorization": "Bearer x"}
        )

    events = _parse_sse(response.text)
    full_text = "".join(e["text"] for e in events if e["type"] == "token")

    assert fake_provider.call_count == 2
    assert full_text == "A real, grounded answer this time."

    retry_attempt_logs = [r.message for r in caplog.records if r.message.startswith("empty_generation_retry ")]
    retry_result_logs = [r.message for r in caplog.records if r.message.startswith("empty_generation_retry_result")]
    assert len(retry_attempt_logs) == 1
    assert "finish_reason=stop" in retry_attempt_logs[0]
    assert len(retry_result_logs) == 1
    assert "retry_finish_reason=stop" in retry_result_logs[0]


def test_truncated_empty_response_does_not_trigger_retry(monkeypatch):
    # finish_reason == "length" is truncation's own signal — this is Fix 1's
    # territory, not the empty-response retry's. An empty completion that was
    # cut off by max_tokens (e.g. all budget spent on something before any
    # visible content streamed) must not be confused with a degenerate
    # zero-content "stop".
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CRISIS))
    fake_provider = _StatefulProvider([([], "length")])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    client.post("/chat", json={"message": "hi", "mode": "crisis"}, headers={"Authorization": "Bearer x"})

    assert fake_provider.call_count == 1


def test_non_empty_first_attempt_does_not_retry(monkeypatch):
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CHANAKYA))
    fake_provider = _StatefulProvider([(["a complete, non-empty answer."], "stop")])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    client.post("/chat", json={"message": "hi", "mode": "chanakya"}, headers={"Authorization": "Bearer x"})

    assert fake_provider.call_count == 1


def test_retry_is_bounded_to_one_attempt_even_if_still_empty(monkeypatch, caplog):
    # Both attempts come back empty — the retry is a single bounded attempt,
    # not a loop. The turn still completes normally (final SSE event, crisis
    # mode's disclaimer still force-appended) rather than hanging or erroring.
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CRISIS))
    fake_provider = _StatefulProvider([([], "stop"), ([], "stop")])
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    with caplog.at_level(logging.WARNING, logger="serving.app"):
        response = client.post(
            "/chat", json={"message": "hi", "mode": "crisis"}, headers={"Authorization": "Bearer x"}
        )

    events = _parse_sse(response.text)
    final_events = [e for e in events if e["type"] == "final"]

    assert fake_provider.call_count == 2  # exactly one retry, not a loop
    assert len(final_events) == 1
    full_text = "".join(e["text"] for e in events if e["type"] == "token")
    assert "This is not legal advice." in full_text  # still force-appended even after a double-empty turn

    retry_result_logs = [r.message for r in caplog.records if r.message.startswith("empty_generation_retry_result")]
    assert "retry_output_chars=0" in retry_result_logs[0]


def test_generation_error_on_first_attempt_does_not_retry(monkeypatch):
    # An exception is a different failure class from an empty completion —
    # already handled distinctly (an {"type": "error"} SSE event), and must
    # not additionally trigger the empty-response retry path.
    monkeypatch.setattr(app_mod, "retrieve_context", lambda *a, **k: _passing_result(Mode.CHANAKYA))
    fake_provider = MagicMock()

    def _raise(*a, **k):
        raise RuntimeError("provider exploded")

    fake_provider.generate.side_effect = _raise
    app_mod.app.dependency_overrides[app_mod.get_provider] = lambda: fake_provider
    client = TestClient(app_mod.app)

    response = client.post(
        "/chat", json={"message": "hi", "mode": "chanakya"}, headers={"Authorization": "Bearer x"}
    )

    events = _parse_sse(response.text)
    assert any(e["type"] == "error" for e in events)
    assert fake_provider.generate.call_count == 1
