"""Upstream errors and the client interfaces the rest of the app depends on."""

from typing import Protocol

from app.integrations.models import BugRecord, DocPassage


class UpstreamError(Exception):
    """Base for failures talking to an internal API. Messages are safe to log, not to show."""

    retryable = False


class UpstreamTimeout(UpstreamError):
    retryable = True


class UpstreamUnavailable(UpstreamError):
    retryable = True


class UpstreamRateLimited(UpstreamError):
    retryable = True

    def __init__(self, message: str = "rate limited", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class UpstreamUnauthorized(UpstreamError):
    """Our service credential was rejected. A server-side config problem, not the user's."""


class UpstreamBadResponse(UpstreamError):
    """Unexpected status, malformed JSON, wrong shape, or an oversized body."""


class BugTrackerClient(Protocol):
    async def get_bug(self, bug_id: str) -> BugRecord | None:
        """Returns None when the bug does not exist."""
        ...


class DocumentationSearchClient(Protocol):
    async def search(self, query: str, *, products: frozenset[str] | None, limit: int = 3) -> list[DocPassage]:
        """products=None means no product filter; an empty set means no access to anything."""
        ...
