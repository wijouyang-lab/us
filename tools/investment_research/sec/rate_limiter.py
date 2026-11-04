"""One process-wide SEC request limiter (Fair Access, no concurrency bypass)."""
from __future__ import annotations
import threading
import time


class RateLimiter:
    def __init__(self, min_interval: float = 0.25, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = max(0.25, float(min_interval))
        self._clock = clock; self._sleep = sleep; self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next - now)
            if delay: self._sleep(delay)
            now = self._clock()
            self._next = now + self.min_interval

    def reset(self) -> None:
        with self._lock: self._next = 0.0


_GLOBAL = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _GLOBAL
