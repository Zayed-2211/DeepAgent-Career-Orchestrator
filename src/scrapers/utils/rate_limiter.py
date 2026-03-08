"""
Token-bucket rate limiter for controlling request frequency.
"""

import time
import threading


class RateLimiter:
    """
    Simple token-bucket rate limiter.
    Blocks the calling thread until a request is allowed.

    Usage:
        limiter = RateLimiter(max_per_minute=30)
        limiter.wait()  # blocks if over budget
        # ... make request ...
    """

    def __init__(self, max_per_minute: int = 30):
        self.max_per_minute = max_per_minute
        self.interval = 60.0 / max_per_minute
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until a request is allowed under the rate limit."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.monotonic()
