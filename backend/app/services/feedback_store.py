"""Minimal feedback records: IDs and a fixed rating/reason. Never email or answer text."""

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class FeedbackRecord:
    request_id: str
    user_id: str
    rating: str
    reason: str | None
    created_at: datetime


class FeedbackStore:
    def __init__(self, max_items: int = 5000) -> None:
        self._items: deque[FeedbackRecord] = deque(maxlen=max_items)

    def add(self, request_id: str, user_id: str, rating: str, reason: str | None) -> None:
        self._items.append(FeedbackRecord(request_id, user_id, rating, reason, datetime.now(UTC)))

    def all(self) -> list[FeedbackRecord]:
        return list(self._items)
