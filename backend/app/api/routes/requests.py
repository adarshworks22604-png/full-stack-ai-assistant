from typing import Any

from fastapi import APIRouter, Depends, Path

from app.api.container import Container
from app.api.dependencies import get_container, get_principal
from app.core.errors import NotFoundError
from app.core.security import Principal
from app.schemas.errors import ErrorResponse
from app.schemas.misc import FeedbackIn, FeedbackOut, RequestStatusOut

router = APIRouter(prefix="/api/v1", tags=["requests"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("/requests/{request_id}", response_model=RequestStatusOut, responses=_ERRORS)
async def request_status(
    request_id: str = Path(pattern=r"^req_[0-9a-f]{32}$"),
    principal: Principal = Depends(get_principal),
    container: Container = Depends(get_container),
) -> RequestStatusOut:
    """Status of one of your own requests. Other users' IDs look the same as unknown ones."""
    record = container.registry.get_for_user(request_id, principal.user_id)
    if record is None:
        raise NotFoundError()
    return RequestStatusOut(request_id=record.request_id, status=record.status, created_at=record.created_at)


@router.post("/feedback", response_model=FeedbackOut, responses=_ERRORS)
async def feedback(
    payload: FeedbackIn,
    principal: Principal = Depends(get_principal),
    container: Container = Depends(get_container),
) -> FeedbackOut:
    """Rating for one of your own requests. Stores IDs and a fixed reason only."""
    if container.registry.get_for_user(payload.request_id, principal.user_id) is None:
        raise NotFoundError()
    container.feedback.add(payload.request_id, principal.user_id, payload.rating, payload.reason)
    return FeedbackOut()
