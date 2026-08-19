"""Piece 5 (serving) — OpenRouter implementation of the GenerationProvider protocol.
Piece 1 (live-verification task) — cost safety rail: explicit max_tokens cap, no
reasoning-effort escalation, per-call usage tracking + running cost estimate.

Generation model: DeepSeek V4 Pro via OpenRouter (senior-approved, see task.md).
Everything OpenRouter-specific — endpoint, model slug, auth header, request/response
shape — is confined to this module; the rest of the serving layer only ever calls
generate(prompt, system, stream) through providers/base.py's protocol, so a future
provider swap is a new file here, not a rewrite elsewhere.

Model slug verified against OpenRouter's own model page
(openrouter.ai/deepseek/deepseek-v4-pro) rather than guessed: "deepseek/deepseek-v4-pro"
is the stable alias OpenRouter keeps pointed at the current GA release (currently
the "-0813" snapshot); dated slugs like "deepseek/deepseek-v4-pro-0813" also exist
for pinning a specific snapshot if that's ever needed — override via the
`openrouter_model` env var, never hardcode a pin here.

Env vars (loaded from the project-root `.env`):
    openrouter_api_key  - OpenRouter API key (required)
    openrouter_model    - model slug override (optional, defaults to deepseek/deepseek-v4-pro)

--- Cost safety rail (live-verification task, Piece 1) --------------------------------
This task makes real, billed OpenRouter calls against a $5 budget. Two things matter
here more than usual:
  1. Every call must cap max_tokens explicitly (default 800 below) — never rely on
     the model's own default ceiling, which could be far larger.
  2. Reasoning is explicitly disabled (`reasoning: {"enabled": false}`), not merely
     left unset. The original plan (Piece 1) was to never set a reasoning param at
     all, on the assumption that "no explicit param" meant reasoning was off by
     default. Piece 2's live smoke test found that assumption was wrong: DeepSeek
     V4 Pro reasons by default, and reasoning tokens count against max_tokens — on
     one real crisis-mode call, the model spent its entire 600-token cap on
     invisible reasoning and returned zero visible answer content. Explicitly
     disabling reasoning (not raising its effort — the opposite) is what task.md's
     own "unless a specific test requires otherwise" exception describes, and is
     the fix, confirmed with the user before making any further live calls.

`OpenRouterProvider` tracks usage per call (from OpenRouter's own `usage` field —
requested via `stream_options.include_usage` for streaming calls, always present
for non-streaming ones) and exposes `total_estimated_cost()`/`print_cost_summary()`
so a live-verification run can print a running total rather than flying blind.

`last_finish_reason` (set from OpenRouter's own `finish_reason`, both sync and
streamed) is how callers detect truncation directly rather than guessing from
content — `"length"` means max_tokens cut the response off mid-generation. See
serving/app.py's truncation handling, added after a real crisis-mode call was
found to truncate silently at the (then-800) cap. `max_tokens` itself is no
longer a single global default here either — serving/mode_config.py's
`ModeConfig.max_tokens` sets it per mode (crisis gets more headroom than
chanakya), threaded through generate()'s `max_tokens` parameter per call.

Pricing note: the constants below are what task.md's budgeting instructions specify.
A live check of OpenRouter's own DeepSeek V4 Pro pricing page during this task showed
a noticeably higher blended/"average price customers pay" rate (~$0.69/M input,
~$1.39/M output, varying by which backend OpenRouter routes to) than these numbers —
flagged in this task's report rather than silently reconciled. The estimate below
uses task.md's stated numbers as instructed; the real total may run higher.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger("providers.openrouter")

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL_ENV_VAR = "openrouter_model"
# The project's .env spells this "open_router_api_key" (extra underscore) rather
# than "openrouter_api_key". We read it as-is rather than silently renaming a file
# we don't own — same convention as db/qdrant_client.py's cahanakya_qdrant_url
# handling. Order matters here: on Windows, os.environ is case-insensitive, and a
# system-level OPENROUTER_API_KEY (a *different* key, for a *different* account)
# was found to already exist outside .env — checking the .env spelling first
# guarantees the intended, budgeted key wins over that collision, not whichever
# env var happens to be case-insensitively equal.
_API_KEY_ENV_VARS = ("open_router_api_key", "openrouter_api_key")
_DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
_DEFAULT_TIMEOUT = 60  # seconds — generation can legitimately take a while but must stay bounded

# Cost safety rail defaults (live-verification task, Piece 1; revised after Piece 2's
# live smoke test found reasoning tokens exhausting the original 600-token cap with
# zero visible output — see module docstring).
DEFAULT_MAX_TOKENS = 800
INPUT_PRICE_PER_MILLION_TOKENS = 0.435  # task.md's stated rate — see module docstring's pricing note
OUTPUT_PRICE_PER_MILLION_TOKENS = 0.87


class OpenRouterError(RuntimeError):
    """Raised on any OpenRouter call failure — HTTP error, timeout, malformed
    response, or an interrupted stream. Deliberately never swallowed: task.md
    requires failing loudly here rather than silently falling back to an
    ungrounded answer."""


def _get_api_key() -> str:
    for var in _API_KEY_ENV_VARS:
        value = os.environ.get(var)
        if value:
            return value
    raise RuntimeError(f"OpenRouter API key not found in .env. Expected one of: {', '.join(_API_KEY_ENV_VARS)}")


def _get_model() -> str:
    return os.environ.get(_MODEL_ENV_VAR, _DEFAULT_MODEL)


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * INPUT_PRICE_PER_MILLION_TOKENS + (
        output_tokens / 1_000_000
    ) * OUTPUT_PRICE_PER_MILLION_TOKENS


class OpenRouterProvider:
    """GenerationProvider implementation backed by OpenRouter's chat completions API."""

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: int = _DEFAULT_TIMEOUT):
        self._model = model or _get_model()
        self._api_key = api_key or _get_api_key()
        self._timeout = timeout
        self.usage_log: list[dict] = []
        # OpenRouter's finish_reason for the most recent call ("stop", "length",
        # ...). "length" means the response was cut off by max_tokens — callers
        # check this after consuming generate()'s return value to detect
        # truncation directly, rather than guessing from content. None until a
        # call actually completes (see _generate_sync/_generate_stream — reset at
        # the start of each call, including the lazy start of a streamed one).
        self.last_finish_reason: str | None = None

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _messages(self, prompt: str, system: str) -> list[dict]:
        return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    def _record_usage(self, usage: dict) -> None:
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = _estimate_cost(input_tokens, output_tokens)
        self.usage_log.append({"input_tokens": input_tokens, "output_tokens": output_tokens, "estimated_cost": cost})
        logger.info(
            "openrouter_usage input_tokens=%d output_tokens=%d estimated_cost=$%.6f running_total=$%.6f",
            input_tokens,
            output_tokens,
            cost,
            self.total_estimated_cost(),
        )

    def total_estimated_cost(self) -> float:
        return sum(entry["estimated_cost"] for entry in self.usage_log)

    def print_cost_summary(self) -> None:
        total_input = sum(entry["input_tokens"] for entry in self.usage_log)
        total_output = sum(entry["output_tokens"] for entry in self.usage_log)
        print(
            f"OpenRouter usage: {len(self.usage_log)} call(s), {total_input} input tokens, "
            f"{total_output} output tokens, estimated cost ${self.total_estimated_cost():.4f}"
        )

    def generate(self, prompt: str, system: str, stream: bool = False, max_tokens: int = DEFAULT_MAX_TOKENS):
        if stream:
            return self._generate_stream(prompt, system, max_tokens)
        return self._generate_sync(prompt, system, max_tokens)

    def _generate_sync(self, prompt: str, system: str, max_tokens: int) -> str:
        self.last_finish_reason = None
        try:
            response = requests.post(
                _API_URL,
                headers=self._headers(),
                json={
                    "model": self._model,
                    "messages": self._messages(prompt, system),
                    "stream": False,
                    "max_tokens": max_tokens,
                    # Explicitly off, not merely unset — see module docstring's
                    # cost-safety-rail note (Piece 2 found this model reasons by
                    # default, burning max_tokens on invisible output).
                    "reasoning": {"enabled": False},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OpenRouterError(f"OpenRouter call failed: {exc}") from exc

        data = response.json()
        usage = data.get("usage")
        if usage:
            self._record_usage(usage)
        try:
            choice = data["choices"][0]
            self.last_finish_reason = choice.get("finish_reason")
            return choice["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise OpenRouterError(f"Unexpected OpenRouter response shape: {data}") from exc

    def _generate_stream(self, prompt: str, system: str, max_tokens: int) -> Iterator[str]:
        # A generator's body doesn't execute until first iterated — so the request,
        # and any failure it raises, happens on the caller's first `next()`/for-loop
        # step, not at generate() call time. Callers must actually iterate to
        # observe a connection failure; that matches how every Iterator[str] caller
        # here already consumes the stream (Piece 6's SSE loop).
        self.last_finish_reason = None
        try:
            response = requests.post(
                _API_URL,
                headers=self._headers(),
                json={
                    "model": self._model,
                    "messages": self._messages(prompt, system),
                    "stream": True,
                    "max_tokens": max_tokens,
                    # Explicitly off, not merely unset — see module docstring's
                    # cost-safety-rail note (Piece 2 found this model reasons by
                    # default, burning max_tokens on invisible output).
                    "reasoning": {"enabled": False},
                    # Requests a final usage-only chunk (empty choices, populated
                    # usage) before [DONE] — without this, streaming responses
                    # carry no token counts at all, and the cost rail is blind.
                    "stream_options": {"include_usage": True},
                },
                timeout=self._timeout,
                stream=True,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OpenRouterError(f"OpenRouter call failed: {exc}") from exc

        # requests only trusts a charset it finds in the Content-Type header;
        # OpenRouter's SSE response doesn't send one, so response.encoding
        # falls back to a guess (historically ISO-8859-1) instead of the
        # UTF-8 the body actually is. Left unset, iter_lines(decode_unicode=
        # True) below decodes every multi-byte UTF-8 character (em-dashes,
        # curly quotes, ...) one byte at a time, mangling it — confirmed live
        # via the React chat UI (Piece 3), which is the first place raw
        # streamed text was actually rendered for a human to read.
        response.encoding = "utf-8"

        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :]
                if payload == "[DONE]":
                    return
                chunk = json.loads(payload)
                usage = chunk.get("usage")
                if usage:
                    self._record_usage(usage)
                choices = chunk.get("choices") or []
                if not choices:
                    continue  # the final usage-only chunk has no choices to read a delta from
                choice = choices[0]
                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    self.last_finish_reason = finish_reason
                delta = choice["delta"].get("content")
                if delta:
                    yield delta
        except requests.RequestException as exc:
            raise OpenRouterError(f"OpenRouter stream interrupted: {exc}") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise OpenRouterError(f"Unexpected OpenRouter stream chunk: {chunk if 'chunk' in locals() else payload!r}") from exc
