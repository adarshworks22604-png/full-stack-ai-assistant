from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.api.container import Container
from app.api.dependencies import get_container, get_principal
from app.api.sse import SSE_HEADERS, event_stream
from app.core.context import get_request_id
from app.core.security import Principal
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.errors import ErrorResponse

router = APIRouter(prefix="/api/v1", tags=["chat"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post("/chat/stream", responses=_ERRORS, response_class=StreamingResponse)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """Start a request and stream progress as Server-Sent Events."""
    request_id = get_request_id()
    admission = container.coordinator.admit(principal)  # 429/503 as JSON, before streaming starts
    events = container.coordinator.run(principal, request_id, payload, admission)
    stream = event_stream(
        request,
        events,
        heartbeat_seconds=container.settings.sse_heartbeat_seconds,
        request_id=request_id,
        on_close=admission.release,
    )
    # The background task also releases the slot if the stream never started (client left early).
    return StreamingResponse(
        stream, media_type="text/event-stream", headers=SSE_HEADERS, background=BackgroundTask(admission.release)
    )


@router.post("/chat", response_model=ChatResponse, responses={**_ERRORS, 504: {"model": ErrorResponse}})
async def chat(
    payload: ChatRequest,
    principal: Principal = Depends(get_principal),
    container: Container = Depends(get_container),
) -> ChatResponse:
    """Non-streaming variant: returns the final answer only."""
    return await container.coordinator.complete(principal, get_request_id(), payload)
