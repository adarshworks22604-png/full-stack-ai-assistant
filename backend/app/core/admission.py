"""Admission control: per-user rate limit and concurrency limits (in-memory).

Single-process only. Move to Redis when running several workers and shared limits are needed.
"""

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.errors import RateLimitedError, ServerBusyError


@dataclass
class Admission:
    """A held slot. release() is idempotent so every exit path can call it."""

    user_id: str
    _controller: "AdmissionController"
    _released: bool = field(default=False, init=False)

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._controller._release(self.user_id)


class AdmissionController:
    def __init__(
        self,
        *,
        rate_limit_per_minute: int,
        max_global: int,
        max_per_user: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rate = rate_limit_per_minute
        self._max_global = max_global
        self._max_user = max_per_user
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._active_by_user: dict[str, int] = {}
        self._active_total = 0

    def admit(self, user_id: str) -> Admission:
        now = self._clock()
        hits = self._hits.setdefault(user_id, deque())
        while hits and now - hits[0] >= 60:
            hits.popleft()
        if len(hits) >= self._rate:
            retry_after = int(60 - (now - hits[0])) + 1
            raise RateLimitedError(retry_after=retry_after)
        if self._active_by_user.get(user_id, 0) >= self._max_user:
            raise RateLimitedError("You already have requests running. Wait for them to finish.", retry_after=2)
        if self._active_total >= self._max_global:
            raise ServerBusyError()
        hits.append(now)
        self._active_by_user[user_id] = self._active_by_user.get(user_id, 0) + 1
        self._active_total += 1
        self._prune(now)
        return Admission(user_id, self)

    def _release(self, user_id: str) -> None:
        remaining = self._active_by_user.get(user_id, 0) - 1
        if remaining <= 0:
            self._active_by_user.pop(user_id, None)
        else:
            self._active_by_user[user_id] = remaining
        self._active_total = max(0, self._active_total - 1)

    def _prune(self, now: float) -> None:
        # Keep memory bounded: drop users with no recent hits and no active requests.
        if len(self._hits) < 1000:
            return
        for user in [
            u for u, h in self._hits.items() if (not h or now - h[-1] >= 60) and u not in self._active_by_user
        ]:
            del self._hits[user]

    @property
    def active_total(self) -> int:
        return self._active_total
