from pydantic import BaseModel


class ValidationIssue(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    request_id: str
    details: list[ValidationIssue] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
