"""SSE event models. Names and fields mirror docs/api-contract.md and frontend/src/types/api.ts."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.schemas.chat import Source

ToolName = Literal["search_documentation", "get_bug_details"]
ToolState = Literal["running", "done", "failed"]
ErrorCode = Literal[
    "RATE_LIMITED",
    "UPSTREAM_TIMEOUT",
    "LLM_UNAVAILABLE",
    "UNAUTHORIZED",
    "INVALID_REQUEST",
    "INTERNAL_ERROR",
]


class RequestStarted(BaseModel):
    type: Literal["request.started"] = "request.started"
    request_id: str
    status: str = "started"


class AssistantDelta(BaseModel):
    type: Literal["assistant.delta"] = "assistant.delta"
    request_id: str
    text: str


class ToolStatus(BaseModel):
    type: Literal["tool.status"] = "tool.status"
    request_id: str
    tool: ToolName
    status: ToolState
    summary: str


class EvidenceReady(BaseModel):
    type: Literal["evidence.ready"] = "evidence.ready"
    request_id: str
    sources: list[Source]


class AssistantFinal(BaseModel):
    type: Literal["assistant.final"] = "assistant.final"
    request_id: str
    answer: str
    sources: list[Source]
    limitations: list[str] = Field(default_factory=list)


class RequestError(BaseModel):
    type: Literal["request.error"] = "request.error"
    request_id: str
    error_code: ErrorCode
    message: str
    retryable: bool


class RequestDone(BaseModel):
    type: Literal["request.done"] = "request.done"
    request_id: str


AnyEvent = RequestStarted | AssistantDelta | ToolStatus | EvidenceReady | AssistantFinal | RequestError | RequestDone
StreamEvent = Annotated[AnyEvent, Field(discriminator="type")]
