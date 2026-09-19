"""In-memory login failure rate limiter.

Sufficient for a single process; use shared storage such as Redis for multi-process / multi-instance deployments.
"""
import threading
import time

from .config import LOGIN_LOCK_MINUTES, LOGIN_MAX_FAILURES


class LoginLimiter:
    def __init__(self, max_failures: int = LOGIN_MAX_FAILURES, lock_minutes: int = LOGIN_LOCK_MINUTES):
        self.max_failures = max_failures
        self.lock_seconds = lock_minutes * 60
        self._lock = threading.Lock()
        # key -> (failure count, timestamp of last failure)
        self._failures: dict[str, tuple[int, float]] = {}

    def _prune(self, now: float) -> None:
        expired = [k for k, (_, ts) in self._failures.items() if now - ts > self.lock_seconds]
        for k in expired:
            del self._failures[k]

    def locked_for(self, key: str) -> int:
        """Return remaining lock seconds if locked, otherwise 0."""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            count, ts = self._failures.get(key, (0, 0.0))
            if count >= self.max_failures:
                return max(1, int(self.lock_seconds - (now - ts)))
            return 0

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            count, _ = self._failures.get(key, (0, 0.0))
            self._failures[key] = (count + 1, now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_limiter = LoginLimiter()
