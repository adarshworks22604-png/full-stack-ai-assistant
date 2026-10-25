"""The chat service interface and the Stage 3 mock implementation.

MockChatService stands in for the AI agent. Stage 5/6 replace it with an LLM-driven orchestrator
behind the same ChatService interface; the API, coordinator and tests stay the same.
It still exercises the real integration clients, authorization checks and failure handling.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Protocol

from app.core.config import Settings
from app.core.security import Principal
from app.integrations.base import BugTrackerClient, DocumentationSearchClient, UpstreamError
from app.integrations.models import BugRecord, DocPassage
from app.schemas.chat import ChatRequest, Source
from app.schemas.events import (
    AssistantDelta,
    AssistantFinal,
    EvidenceReady,
    RequestError,
    RequestStarted,
    ToolStatus,
)
from app.services.authorization import AccessPolicy
from app.services.bug_ids import extract_bug_ids

log = logging.getLogger(__name__)
MAX_BUG_IDS = 3
# Events the chat service may emit. The coordinator adds the final `request.done`.
ChatEvent = RequestStarted | AssistantDelta | ToolStatus | EvidenceReady | AssistantFinal | RequestError


class ChatService(Protocol):
    def stream(self, principal: Principal, request_id: str, payload: ChatRequest) -> AsyncIterator[ChatEvent]: ...


class MockChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        bugs: BugTrackerClient,
        docs: DocumentationSearchClient,
        policy: AccessPolicy,
    ) -> None:
        self._settings = settings
        self._bugs = bugs
        self._docs = docs
        self._policy = policy

    async def _pause(self, factor: float = 1.0) -> None:
        delay = self._settings.mock_step_delay_seconds * factor
        if delay > 0:
            await asyncio.sleep(delay)

    async def stream(self, principal: Principal, request_id: str, payload: ChatRequest) -> AsyncIterator[ChatEvent]:
        rid = request_id
        yield RequestStarted(request_id=rid)
        await self._pause(0.5)

        if "simulate error" in payload.message.lower():
            yield RequestError(
                request_id=rid,
                error_code="UPSTREAM_TIMEOUT",
                message="The bug tracker took too long to respond. Try again in a moment.",
                retryable=True,
            )
            return

        # Email text is untrusted data: it is only scanned for IDs, never interpreted as instructions.
        email = payload.email_context
        haystack = f"{email.subject if email else ''}\n{email.body_text if email else ''}\n{payload.message}"
        ids = extract_bug_ids(haystack, self._settings.bug_id_pattern, MAX_BUG_IDS)

        if not ids:
            yield AssistantFinal(
                request_id=rid,
                answer=(
                    "I couldn't find a bug ID in this email. "
                    "Tell me which bug you mean (for example BUG-1234) and I'll look it up."
                ),
                sources=[],
                limitations=["No bug ID was detected, so nothing was looked up."],
            )
            return

        preliminary = (
            f"This email mentions {' and '.join(ids)}. I'm checking the bug record and the documentation "
            "before saying anything about cause or status."
        )
        for word in preliminary.split(" "):
            yield AssistantDelta(request_id=rid, text=word + " ")
        yield ToolStatus(request_id=rid, tool="get_bug_details", status="running", summary=f"Checking {', '.join(ids)}")
        yield ToolStatus(
            request_id=rid, tool="search_documentation", status="running", summary="Searching documentation"
        )
        await self._pause(1.5)

        # Independent read-only lookups run concurrently; one failing does not stop the others.
        results = await asyncio.gather(*(self._lookup(principal, b) for b in ids))
        found: list[BugRecord] = [r for r in results if isinstance(r, BugRecord)]
        unreachable = [b for b, r in zip(ids, results, strict=True) if isinstance(r, UpstreamError)]
        missing = [b for b, r in zip(ids, results, strict=True) if r is None]

        bug_sources = [Source(source_id=b.id, source_type="bug", title=f"{b.id}: {b.title}") for b in found]
        if found:
            bug_summary = f"Found {', '.join(b.id for b in found)}"
        elif unreachable:
            bug_summary = "Bug tracker unavailable"
        else:
            bug_summary = f"{', '.join(missing)} not found"
        yield ToolStatus(
            request_id=rid, tool="get_bug_details", status="done" if found else "failed", summary=bug_summary
        )
        if bug_sources:
            yield EvidenceReady(request_id=rid, sources=bug_sources)
        await self._pause(1)

        passages: list[DocPassage] = []
        docs_failed = False
        if found:
            query = " ".join(b.title for b in found)
            try:
                passages = await self._docs.search(query, products=self._policy.allowed_products(principal), limit=3)
            except UpstreamError as exc:
                log.warning("documentation search failed: %s", type(exc).__name__)
                docs_failed = True
        yield ToolStatus(
            request_id=rid,
            tool="search_documentation",
            status="failed" if docs_failed else "done",
            summary=(
                "Documentation search unavailable"
                if docs_failed
                else f"{len(passages)} relevant passage(s)"
                if passages
                else "No relevant documentation"
                if found
                else "Not searched: no bug record found"
            ),
        )
        doc_sources = [
            Source(source_id=p.source_id, source_type="documentation", title=p.title, uri=p.uri) for p in passages
        ]
        if doc_sources:
            yield EvidenceReady(request_id=rid, sources=doc_sources)
        await self._pause(1)

        parts: list[str] = []
        for bug in found:
            fix = f" Fix: {bug.resolution}" if bug.resolution else " No resolution is recorded yet."
            parts.append(f"{bug.id} ({bug.title}) is {bug.status}.{fix} [{bug.id}]")
        for p in passages:
            parts.append(f"Related guidance: {p.excerpt} [{p.source_id}]")
        for b in missing:
            parts.append(
                f"I couldn't find {b} in the bug tracker, or you may not have access to it, "
                "so I can't confirm its status or cause."
            )
        for b in unreachable:
            parts.append(f"I couldn't reach the bug tracker for {b}, so I can't confirm its status or cause.")

        limitations = [f"{b} was not found, or you may not have access to it." for b in missing]
        limitations += [f"The bug tracker could not be reached for {b}." for b in unreachable]
        if docs_failed:
            limitations.append("Documentation search was unavailable.")
        elif found and not passages:
            limitations.append("No documentation matched this question.")

        yield AssistantFinal(
            request_id=rid, answer="\n\n".join(parts), sources=bug_sources + doc_sources, limitations=limitations
        )

    async def _lookup(self, principal: Principal, bug_id: str) -> BugRecord | None | UpstreamError:
        try:
            bug = await self._bugs.get_bug(bug_id)
        except UpstreamError as exc:
            log.warning("bug lookup failed: %s", type(exc).__name__)
            return exc
        # Authorization in code. Inaccessible and nonexistent look the same to the user.
        if bug is not None and not self._policy.can_access_product(principal, bug.product):
            return None
        return bug
