import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.common import StrictModel

MAX_MESSAGE_CHARS = 8_000
MAX_SUBJECT_CHARS = 500
MAX_BODY_CHARS = 8_000

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: str) -> str:
    """Drop control characters (keeps tab/newline/carriage return)."""
    return _CONTROL.sub("", value)


Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_CHARS)]
Subject = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_SUBJECT_CHARS)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_BODY_CHARS)]
ConversationId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class EmailContextIn(StrictModel):
    subject: Subject
    body_text: Body

    @field_validator("subject", "body_text", mode="after")
    @classmethod
    def _strip_controls(cls, v: str) -> str:
        return _clean(v)


class ChatRequest(StrictModel):
    message: Message
    email_context: EmailContextIn | None = None
    conversation_id: ConversationId | None = None

    @field_validator("message", mode="after")
    @classmethod
    def _strip_controls(cls, v: str) -> str:
        cleaned = _clean(v).strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned


SourceType = Literal["bug", "documentation"]


class Source(BaseModel):
    source_id: str
    source_type: SourceType
    title: str
    uri: str | None = None


class ChatResponse(BaseModel):
    """Non-streaming result of POST /api/v1/chat."""

    request_id: str
    status: Literal["complete"] = "complete"
    answer: str
    sources: list[Source]
    limitations: list[str] = Field(default_factory=list)
