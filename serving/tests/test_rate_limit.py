import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # project root

from serving.rate_limit import GenerationConcurrencyLimiter, InMemoryTokenBucketLimiter


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --- InMemoryTokenBucketLimiter ------------------------------------------------------


def test_allows_up_to_max_requests_then_blocks():
    clock = _FakeClock()
    limiter = InMemoryTokenBucketLimiter(max_requests=3, window_seconds=60, time_fn=clock)

    for _ in range(3):
        allowed, retry_after = limiter.allow("client_a")
        assert allowed is True
        assert retry_after == 0.0

    allowed, retry_after = limiter.allow("client_a")  # the N+1th request within the window
    assert allowed is False
    assert retry_after > 0.0


def test_window_reset_allows_requests_again():
    clock = _FakeClock()
    limiter = InMemoryTokenBucketLimiter(max_requests=2, window_seconds=60, time_fn=clock)

    assert limiter.allow("client_a") == (True, 0.0)
    assert limiter.allow("client_a") == (True, 0.0)
    allowed, _ = limiter.allow("client_a")
    assert allowed is False

    clock.advance(60)  # a full window's worth of refill

    allowed, retry_after = limiter.allow("client_a")
    assert allowed is True
    assert retry_after == 0.0


def test_partial_refill_is_proportional_not_all_or_nothing():
    clock = _FakeClock()
    limiter = InMemoryTokenBucketLimiter(max_requests=6, window_seconds=60, time_fn=clock)

    for _ in range(6):
        assert limiter.allow("client_a")[0] is True
    assert limiter.allow("client_a")[0] is False

    clock.advance(10)  # 1/6th of the window -> ~1 token back

    assert limiter.allow("client_a")[0] is True
    assert limiter.allow("client_a")[0] is False  # only ~1 token was refilled, not the full bucket


def test_rate_limit_is_scoped_per_client():
    clock = _FakeClock()
    limiter = InMemoryTokenBucketLimiter(max_requests=1, window_seconds=60, time_fn=clock)

    assert limiter.allow("client_a") == (True, 0.0)
    assert limiter.allow("client_a")[0] is False  # client A is now limited

    allowed_b, retry_after_b = limiter.allow("client_b")
    assert allowed_b is True  # client B is unaffected by client A's limit
    assert retry_after_b == 0.0


# --- GenerationConcurrencyLimiter -----------------------------------------------------


def test_generation_limiter_allows_up_to_max_concurrent():
    limiter = GenerationConcurrencyLimiter(max_concurrent=2)

    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False  # third concurrent slot is over the cap


def test_generation_limiter_frees_a_slot_on_release():
    limiter = GenerationConcurrencyLimiter(max_concurrent=1)

    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False

    limiter.release()

    assert limiter.try_acquire() is True
