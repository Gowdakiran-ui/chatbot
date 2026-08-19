"""Tests for providers/openrouter.py — requests.post is monkeypatched throughout,
so no live OpenRouter API key or network call is needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

import pytest
import requests

from providers.base import GenerationProvider
from providers.openrouter import DEFAULT_MAX_TOKENS, OpenRouterError, OpenRouterProvider


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, lines=None, raise_exc=None):
        self.status_code = status_code
        self._json_data = json_data
        self._lines = lines or []
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data

    def iter_lines(self, decode_unicode=True):
        yield from self._lines


@pytest.fixture
def provider():
    return OpenRouterProvider(model="deepseek/deepseek-v4-pro", api_key="test-key")


def test_provider_satisfies_generation_provider_protocol(provider):
    assert isinstance(provider, GenerationProvider)


def test_generate_sync_returns_content(monkeypatch, provider):
    captured = {}

    def fake_post(url, headers, json, timeout, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(json_data={"choices": [{"message": {"content": "grounded answer"}}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    result = provider.generate("the prompt", "the system", stream=False)

    assert result == "grounded answer"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "deepseek/deepseek-v4-pro"
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "the system"},
        {"role": "user", "content": "the prompt"},
    ]


def test_generate_sync_raises_openrouter_error_on_http_failure(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(status_code=500)

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    with pytest.raises(OpenRouterError):
        provider.generate("prompt", "system", stream=False)


def test_generate_sync_raises_openrouter_error_on_timeout(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    with pytest.raises(OpenRouterError):
        provider.generate("prompt", "system", stream=False)


def test_generate_sync_raises_openrouter_error_on_malformed_response(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(json_data={"unexpected": "shape"})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    with pytest.raises(OpenRouterError):
        provider.generate("prompt", "system", stream=False)


def test_generate_stream_yields_content_chunks_in_order(monkeypatch, provider):
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}',
        "",  # blank keep-alive lines are common in real SSE streams and must be skipped
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        "data: [DONE]",
    ]

    def fake_post(url, headers, json, timeout, stream, **kwargs):
        assert stream is True
        assert json["stream"] is True
        return _FakeResponse(lines=sse_lines)

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    chunks = list(provider.generate("prompt", "system", stream=True))

    assert chunks == ["Hello", " world"]


def test_generate_stream_raises_on_connection_failure_when_iterated(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    stream = provider.generate("prompt", "system", stream=True)
    with pytest.raises(OpenRouterError):
        next(stream)


def test_generate_stream_raises_on_malformed_chunk(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(lines=["data: not valid json"])

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    stream = provider.generate("prompt", "system", stream=True)
    with pytest.raises(OpenRouterError):
        next(stream)


def test_model_and_api_key_come_from_env_not_hardcoded(monkeypatch):
    # open_router_api_key (the real .env spelling) takes priority — see
    # test_dotenv_spelling_of_api_key_takes_priority_over_the_other_name below.
    monkeypatch.setenv("open_router_api_key", "env-key-123")
    monkeypatch.setenv("openrouter_model", "deepseek/deepseek-v4-pro-0813")

    provider = OpenRouterProvider()

    assert provider._api_key == "env-key-123"
    assert provider._model == "deepseek/deepseek-v4-pro-0813"


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("openrouter_api_key", raising=False)
    monkeypatch.delenv("open_router_api_key", raising=False)

    with pytest.raises(RuntimeError, match="open_router_api_key"):
        OpenRouterProvider()


def test_api_key_reads_the_actual_dotenv_spelling(monkeypatch):
    """The project's real .env spells this "open_router_api_key" (extra
    underscore) — confirm that spelling is read, not just the no-underscore one."""
    monkeypatch.delenv("openrouter_api_key", raising=False)
    monkeypatch.setenv("open_router_api_key", "dotenv-spelled-key")

    provider = OpenRouterProvider()

    assert provider._api_key == "dotenv-spelled-key"


def test_dotenv_spelling_of_api_key_takes_priority_over_the_other_name(monkeypatch):
    """Regression test for a real bug found live: Windows env vars are
    case-insensitive, and a pre-existing system-level OPENROUTER_API_KEY (a
    different key entirely) was silently winning over the .env-configured one.
    The .env spelling must be checked first."""
    monkeypatch.setenv("open_router_api_key", "correct-dotenv-key")
    monkeypatch.setenv("openrouter_api_key", "wrong-other-key")

    provider = OpenRouterProvider()

    assert provider._api_key == "correct-dotenv-key"


# --- Cost safety rail (live-verification task, Piece 1) ------------------------------


def test_generate_sync_sends_default_max_tokens_cap(monkeypatch, provider):
    captured = {}

    def fake_post(url, headers, json, timeout, **kwargs):
        captured["json"] = json
        return _FakeResponse(json_data={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)

    assert captured["json"]["max_tokens"] == DEFAULT_MAX_TOKENS == 800


def test_generate_sync_respects_explicit_max_tokens_override(monkeypatch, provider):
    captured = {}

    def fake_post(url, headers, json, timeout, **kwargs):
        captured["json"] = json
        return _FakeResponse(json_data={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False, max_tokens=50)

    assert captured["json"]["max_tokens"] == 50


def test_generate_explicitly_disables_reasoning(monkeypatch, provider):
    """Reasoning must be explicitly turned off, not merely left unset — see the
    cost-safety-rail note in the module docstring. This is a real live-verification
    finding: DeepSeek V4 Pro reasons by default, and a real call once spent its
    entire max_tokens cap on invisible reasoning with zero visible output."""
    captured = {}

    def fake_post(url, headers, json, timeout, **kwargs):
        captured["json"] = json
        return _FakeResponse(json_data={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)

    assert captured["json"]["reasoning"] == {"enabled": False}
    assert "reasoning_effort" not in captured["json"]


def test_generate_stream_also_explicitly_disables_reasoning(monkeypatch, provider):
    captured = {}

    def fake_post(url, headers, json, timeout, stream, **kwargs):
        captured["json"] = json
        return _FakeResponse(lines=["data: [DONE]"])

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    list(provider.generate("prompt", "system", stream=True))

    assert captured["json"]["reasoning"] == {"enabled": False}


def test_generate_stream_requests_usage_via_stream_options(monkeypatch, provider):
    captured = {}

    def fake_post(url, headers, json, timeout, stream, **kwargs):
        captured["json"] = json
        return _FakeResponse(lines=["data: [DONE]"])

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    list(provider.generate("prompt", "system", stream=True))

    assert captured["json"]["stream_options"] == {"include_usage": True}
    assert captured["json"]["max_tokens"] == DEFAULT_MAX_TOKENS == 800


def test_generate_sync_records_usage_and_estimates_cost(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(
            json_data={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            }
        )

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)

    assert provider.usage_log == [{"input_tokens": 1000, "output_tokens": 500, "estimated_cost": pytest.approx(0.000870)}]
    assert provider.total_estimated_cost() == pytest.approx(0.000870)


def test_generate_stream_records_usage_from_final_chunk_without_yielding_it_as_content(monkeypatch, provider):
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        # Final usage-only chunk: empty choices, per OpenRouter's documented
        # stream_options.include_usage behavior — must not crash on choices[0].
        'data: {"choices":[],"usage":{"prompt_tokens":200,"completion_tokens":80}}',
        "data: [DONE]",
    ]

    def fake_post(*args, **kwargs):
        return _FakeResponse(lines=sse_lines)

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    chunks = list(provider.generate("prompt", "system", stream=True))

    assert chunks == ["Hello"]  # the usage-only chunk contributed no content
    assert provider.usage_log == [{"input_tokens": 200, "output_tokens": 80, "estimated_cost": pytest.approx(0.0001566)}]


def test_total_estimated_cost_sums_across_multiple_calls(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(
            json_data={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0},
            }
        )

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)
    provider.generate("prompt", "system", stream=False)

    assert provider.total_estimated_cost() == pytest.approx(0.87)  # 2 x 1M input tokens @ $0.435/M


def test_print_cost_summary_reports_totals(monkeypatch, provider, capsys):
    def fake_post(*args, **kwargs):
        return _FakeResponse(
            json_data={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
        )

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)
    provider.print_cost_summary()

    out = capsys.readouterr().out
    assert "1 call" in out
    assert "100 input tokens" in out
    assert "50 output tokens" in out


# --- last_finish_reason (generation-quality fixes task, Fix 1) -----------------------


def test_last_finish_reason_starts_none(provider):
    assert provider.last_finish_reason is None


def test_generate_sync_sets_last_finish_reason_stop(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(json_data={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)

    assert provider.last_finish_reason == "stop"


def test_generate_sync_sets_last_finish_reason_length_on_truncation(monkeypatch, provider):
    def fake_post(*args, **kwargs):
        return _FakeResponse(json_data={"choices": [{"message": {"content": "cut off"}, "finish_reason": "length"}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    provider.generate("prompt", "system", stream=False)

    assert provider.last_finish_reason == "length"


def test_generate_stream_sets_last_finish_reason_from_final_chunk(monkeypatch, provider):
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"length"}]}',
        "data: [DONE]",
    ]

    def fake_post(*args, **kwargs):
        return _FakeResponse(lines=sse_lines)

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post)

    list(provider.generate("prompt", "system", stream=True))

    assert provider.last_finish_reason == "length"


def test_last_finish_reason_resets_between_calls(monkeypatch, provider):
    def fake_post_length(*args, **kwargs):
        return _FakeResponse(json_data={"choices": [{"message": {"content": "cut"}, "finish_reason": "length"}]})

    def fake_post_stop(*args, **kwargs):
        return _FakeResponse(json_data={"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]})

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post_length)
    provider.generate("prompt", "system", stream=False)
    assert provider.last_finish_reason == "length"

    monkeypatch.setattr("providers.openrouter.requests.post", fake_post_stop)
    provider.generate("prompt", "system", stream=False)
    assert provider.last_finish_reason == "stop"
