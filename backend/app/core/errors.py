"""Application errors. Each maps to one stable HTTP status + error code.

Messages here are shown to API clients, so they must never contain secrets,
stack traces, internal hostnames or raw upstream responses.
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Something went wrong on our side. Try again."
    retryable: bool = False

    def __init__(self, message: str | None = None, *, headers: dict[str, str] | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.headers = headers or {}


class AuthenticationError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Sign in again to continue."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You don't have access to this."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Not found."


class InvalidRequestError(AppError):
    status_code = 422
    code = "INVALID_REQUEST"
    message = "The request is not valid."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"
    message = "The request is too large."


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many requests. Wait a moment and try again."
    retryable = True

    def __init__(self, message: str | None = None, *, retry_after: int = 1) -> None:
        super().__init__(message, headers={"Retry-After": str(max(1, retry_after))})


class ServerBusyError(AppError):
    status_code = 503
    code = "SERVER_BUSY"
    message = "The assistant is busy. Try again in a moment."
    retryable = True

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, headers={"Retry-After": "5"})


class UpstreamTimeoutError(AppError):
    status_code = 504
    code = "UPSTREAM_TIMEOUT"
    message = "A data source took too long to respond. Try again."
    retryable = True


class LlmUnavailableError(AppError):
    status_code = 503
    code = "LLM_UNAVAILABLE"
    message = "The language model is unavailable. Try again later."
    retryable = True


# SSE `request.error` codes -> HTTP status, used by the non-streaming endpoint.
ERROR_CODE_STATUS = {
    "UPSTREAM_TIMEOUT": 504,
    "LLM_UNAVAILABLE": 503,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
}
