from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.container import Container, build_container
from app.api.error_handlers import register_exception_handlers
from app.api.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from app.api.routes import chat, health, requests
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.aclose()  # close pooled HTTP connections on shutdown

    app = FastAPI(
        title="Outlook Engineering AI Assistant",
        version="0.1.0",
        lifespan=lifespan,
        # Interactive docs stay available locally only.
        docs_url="/docs" if settings.app_env == "local" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env == "local" else None,
    )
    app.state.container = container

    register_exception_handlers(app)
    # add_middleware wraps outward: the last one added is the outermost.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(requests.router)
    return app


def get_app() -> FastAPI:
    """Factory entry point: `uvicorn app.main:get_app --factory`."""
    return create_app()
