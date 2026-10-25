from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.container import Container
from app.api.dependencies import get_container
from app.schemas.misc import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    """The process is running. No dependency details."""
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def ready(container: Container = Depends(get_container)) -> HealthResponse | JSONResponse:
    """Ready to serve traffic. Reports only ready / not_ready, never internals."""
    healthy = container.verifier is not None and container.coordinator is not None
    if not healthy:
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return HealthResponse(status="ready")
