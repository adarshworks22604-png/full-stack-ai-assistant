"""Pure-ASGI middleware (safe with streaming responses).

RequestContextMiddleware: generates the request ID server-side (a client-sent X-Request-ID is
ignored), adds security headers, and writes one access-log line without query strings or bodies.
BodySizeLimitMiddleware: rejects oversized bodies, including chunked uploads without Content-Length.
"""

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.error_handlers import error_response
from app.core.context import request_id_var
from app.core.errors import AppError, PayloadTooLargeError

log = logging.getLogger("app.access")

SECURITY_HEADERS = {
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"no-referrer",
    b"cache-control": b"no-store",
}


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = f"req_{uuid.uuid4().hex}"
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_holder = {"status": 500}
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                headers.append((b"x-request-id", request_id.encode()))
                for key, value in SECURITY_HEADERS.items():
                    if key not in existing:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:  # noqa: BLE001
            # Handled here, inside the request context, so the 500 carries the request ID and the
            # traceback is logged server-side only. Starlette's outer handler runs after the context is gone.
            log.exception("unhandled error")
            if not response_started:
                status_holder["status"] = 500
                await error_response(AppError())(scope, receive, send_wrapper)
        finally:
            log.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_holder["status"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Enforces a maximum request body size.

    Content-Length is checked up front. Bodies without it (chunked uploads) are buffered up to the
    limit and replayed to the app, so an oversized upload gets a clean 413 instead of reaching a route.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await self._reject(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        buffered = b"".join(chunks)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        await error_response(PayloadTooLargeError())(scope, receive, send)
