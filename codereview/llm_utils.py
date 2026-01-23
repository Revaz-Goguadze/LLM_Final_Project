import time
import threading


class RateLimiter:
    """Thread-safe rate limiter with a minimum delay between calls."""

    def __init__(self, min_delay_seconds: float):
        self.min_delay_seconds = max(0.0, min_delay_seconds)
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.min_delay_seconds <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_delay_seconds:
                time.sleep(self.min_delay_seconds - elapsed)
            self._last_call = time.monotonic()


def should_retry(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    return any(
        token in lowered
        for token in ["rate limit", "429", "resource exhausted", "temporarily", "timeout"]
    )


def backoff_sleep(attempt: int, base: float = 1.0, cap: float = 20.0) -> None:
    delay = min(cap, base * (2 ** max(0, attempt)))
    time.sleep(delay)
