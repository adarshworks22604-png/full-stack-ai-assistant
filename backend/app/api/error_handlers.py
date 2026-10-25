"""Centralized error handling: one JSON shape for every failure, no internals exposed."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import get_request_id
from app.core.errors import AppError
from app.schemas.errors import ErrorBody, ErrorResponse, ValidationIssue

log = logging.getLogger(__name__)

_HTTP_CODES = {
    400: ("INVALID_REQUEST", "The request is not valid."),
    401: ("UNAUTHORIZED", "Sign in again to continue."),
    403: ("FORBIDDEN", "You don't have access to this."),
    404: ("NOT_FOUND", "Not found."),
    405: ("METHOD_NOT_ALLOWED", "That method isn't supported here."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Send the request as JSON."),
}


def error_response(
    error: AppError, details: list[ValidationIssue] | None = None, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
            request_id=get_request_id(),
            details=details,
        )
    )
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=error.status_code, headers=headers or error.headers
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Report where and why, never the submitted value (it may be email content or a secret).
        issues = [
            ValidationIssue(field=".".join(str(p) for p in e["loc"] if p != "body") or "body", message=str(e["msg"]))
            for e in exc.errors()[:10]
        ]
        from app.core.errors import InvalidRequestError

        return error_response(InvalidRequestError(), details=issues)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("HTTP_ERROR", "The request could not be completed."))
        err = AppError(message)
        err.status_code, err.code = exc.status_code, code
        return error_response(err, headers=dict(exc.headers or {}))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")  # full traceback stays in server logs
        return error_response(AppError())
