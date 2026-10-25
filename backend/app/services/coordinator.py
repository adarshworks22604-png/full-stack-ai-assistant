"""ChatCoordinator: owns the lifecycle of one chat request.

Admission (rate/concurrency limits) -> registry entry -> run the chat service under a deadline ->
map failures to safe error events -> always finish with `request.done` -> release resources.
Routes stay thin; all of this is testable without HTTP.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from app.core.admission import Admission, AdmissionController
from app.core.config import Settings
from app.core.errors import ERROR_CODE_STATUS, AppError
from app.core.security import Principal
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.events import AssistantFinal, RequestDone, RequestError, StreamEvent
from app.services.chat_service import ChatService
from app.services.request_registry import RequestRegistry, Status

log = logging.getLogger(__name__)


class ChatCoordinator:
    def __init__(
        self,
        *,
        chat_service: ChatService,
        registry: RequestRegistry,
        admission: AdmissionController,
        settings: Settings,
    ) -> None:
        self._chat = chat_service
        self._registry = registry
        self._admission = admission
        self._settings = settings

    @property
    def active_requests(self) -> int:
        return self._admission.active_total

    def admit(self, principal: Principal) -> Admission:
        """Raises RateLimitedError / ServerBusyError (HTTP 429/503) before any work starts."""
        return self._admission.admit(principal.user_id)

    async def run(
        self, principal: Principal, request_id: str, payload: ChatRequest, admission: Admission
    ) -> AsyncIterator[StreamEvent]:
        self._registry.create(request_id, principal.user_id)
        status: Status = "cancelled"  # stays this way if the consumer goes away early
        try:
            try:
                async with asyncio.timeout(self._settings.request_timeout_seconds):
                    async for event in self._chat.stream(principal, request_id, payload):
                        if event.type == "assistant.final":
                            status = "complete"
                        elif event.type == "request.error":
                            status = "failed"
                        yield event
                if status == "cancelled":  # stream ended without a terminal event
                    status = "failed"
                    yield RequestError(
                        request_id=request_id,
                        error_code="INTERNAL_ERROR",
                        message="The assistant stopped before finishing. Try again.",
                        retryable=True,
                    )
            except TimeoutError:
                status = "failed"
                log.warning("request exceeded its deadline")
                yield RequestError(
                    request_id=request_id,
                    error_code="UPSTREAM_TIMEOUT",
                    message="This is taking too long. Try again.",
                    retryable=True,
                )
            except Exception:  # noqa: BLE001 - never leak details; log them server-side
                status = "failed"
                log.exception("chat request failed")
                yield RequestError(
                    request_id=request_id,
                    error_code="INTERNAL_ERROR",
                    message="Something went wrong on our side. Try again.",
                    retryable=True,
                )
            yield RequestDone(request_id=request_id)
        finally:
            self._registry.update(request_id, status)
            admission.release()

    async def complete(self, principal: Principal, request_id: str, payload: ChatRequest) -> ChatResponse:
        """Non-streaming variant: run to the end and return the final answer or raise a safe error."""
        admission = self.admit(principal)
        final: AssistantFinal | None = None
        error: RequestError | None = None
        async for event in self.run(principal, request_id, payload, admission):
            if isinstance(event, AssistantFinal):
                final = event
            elif isinstance(event, RequestError):
                error = event
        if final is not None:
            return ChatResponse(
                request_id=request_id, answer=final.answer, sources=final.sources, limitations=final.limitations
            )
        code = error.error_code if error else "INTERNAL_ERROR"
        raise _error_for(code, error.message if error else None, error.retryable if error else False)


def _error_for(code: str, message: str | None, retryable: bool) -> AppError:
    err = AppError(message)
    err.status_code = ERROR_CODE_STATUS.get(code, 500)
    err.code = code
    err.retryable = retryable
    return err
