"""Piece 2 of the security/auth hardening task — rate limiting.

Two independent, differently-scoped limits:

1. `InMemoryTokenBucketLimiter` — a per-client token bucket (N requests/window),
   checked in serving/app.py *before* retrieval runs at all, so a rate-limited
   request never costs a Qdrant query.
2. `GenerationConcurrencyLimiter` — a single *global* (not per-client) cap on
   in-flight generation calls specifically, not retrieval. Generation is the
   slow, expensive part once the OpenRouter key is live, and the thing most
   likely to let one client's burst degrade every other client's latency.

Both are in-memory and process-local — correct for a single instance, which is
this project's actual pre-launch scale (see serving/auth.py's docstring for the
same reasoning). `InMemoryTokenBucketLimiter` implements the `RateLimiterBackend`
protocol below specifically so that swapping to a shared backend (Redis, once this
runs on more than one instance — in-memory state can't be correct across
processes) is a new class satisfying the same interface, not a rewrite of
serving/app.py's call sites.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Protocol


class RateLimiterBackend(Protocol):
    def allow(self, key: str) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds). retry_after_seconds is 0.0 when
        allowed is True."""
        ...


class InMemoryTokenBucketLimiter:
    """One token bucket per key, refilled continuously at max_requests/window_seconds
    tokens per second. Not safe across multiple processes/instances — see module
    docstring.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self._max_requests = max_requests
        self._refill_rate = max_requests / window_seconds  # tokens per second
        self._time_fn = time_fn
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill_ts)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, float]:
        now = self._time_fn()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self._max_requests), now))
            tokens = min(self._max_requests, tokens + (now - last) * self._refill_rate)

            if tokens >= 1:
                self._buckets[key] = (tokens - 1, now)
                return True, 0.0

            self._buckets[key] = (tokens, now)
            retry_after = (1 - tokens) / self._refill_rate
            return False, retry_after


class GenerationConcurrencyLimiter:
    """A global semaphore-backed cap on in-flight generation calls. try_acquire()
    is non-blocking — a request that can't get a slot should fail fast with a 429,
    not queue silently and degrade every other in-flight request's latency."""

    def __init__(self, max_concurrent: int):
        self._semaphore = threading.Semaphore(max_concurrent)

    def try_acquire(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        self._semaphore.release()
