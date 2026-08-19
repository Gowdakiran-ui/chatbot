"""Piece 5 — generation provider protocol.

The serving layer calls `GenerationProvider.generate()` and nothing more specific
than that. This project has already pivoted LLM/embedding provider choice twice
(see CLAUDE.md) — a future swap should mean adding a new module under providers/
that satisfies this protocol, not touching serving code.
"""
from __future__ import annotations

from typing import Iterator, Protocol, Union, runtime_checkable


@runtime_checkable
class GenerationProvider(Protocol):
    #: The finish reason from the most recently completed generate() call
    #: ("stop", "length", ...) — "length" means the response was cut off by
    #: max_tokens. Callers check this *after* consuming generate()'s return
    #: value to detect truncation directly, not by guessing from content.
    #: None before any call has completed.
    last_finish_reason: str | None

    def generate(
        self, prompt: str, system: str, stream: bool = False, max_tokens: int = 600
    ) -> Union[Iterator[str], str]:
        """Returns the full response text if stream=False, or an iterator of text
        chunks (as they arrive) if stream=True. Must raise on failure — callers are
        never meant to receive a silently degraded or fabricated answer.

        max_tokens is a real cap, not advisory — implementations must pass it
        through to the underlying provider rather than relying on that provider's
        own default ceiling (see providers/openrouter.py's cost-safety-rail note,
        added for the live-verification task)."""
        ...
