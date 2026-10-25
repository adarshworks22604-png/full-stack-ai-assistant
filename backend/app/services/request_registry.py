"""In-memory record of recent requests, so status/feedback can be checked per user.

Bounded in size and age. Replace with a database table when durability is needed.
"""

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

Status = Literal["running", "complete", "failed", "cancelled"]


@dataclass
class RequestRecord:
    request_id: str
    user_id: str
    status: Status
    created_at: datetime
    _created_mono: float


class RequestRegistry:
    def __init__(
        self, *, max_items: int = 1000, ttl_seconds: float = 3600, clock: Callable[[], float] = time.monotonic
    ):
        self._items: OrderedDict[str, RequestRecord] = OrderedDict()
        self._max = max_items
        self._ttl = ttl_seconds
        self._clock = clock

    def create(self, request_id: str, user_id: str) -> None:
        self._evict()
        self._items[request_id] = RequestRecord(request_id, user_id, "running", datetime.now(UTC), self._clock())
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def update(self, request_id: str, status: Status) -> None:
        record = self._items.get(request_id)
        if record:
            record.status = status

    def get_for_user(self, request_id: str, user_id: str) -> RequestRecord | None:
        """Returns None for unknown IDs and for other users' IDs alike (no existence leak)."""
        self._evict()
        record = self._items.get(request_id)
        return record if record and record.user_id == user_id else None

    def _evict(self) -> None:
        now = self._clock()
        while self._items:
            oldest = next(iter(self._items.values()))
            if now - oldest._created_mono < self._ttl:
                break
            self._items.popitem(last=False)
