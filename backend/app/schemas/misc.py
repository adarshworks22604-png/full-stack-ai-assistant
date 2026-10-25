from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.schemas.common import StrictModel

RequestIdStr = Annotated[str, StringConstraints(pattern=r"^req_[0-9a-f]{32}$")]


class HealthResponse(BaseModel):
    status: Literal["ok", "ready", "not_ready"]


class FeedbackIn(StrictModel):
    request_id: RequestIdStr
    rating: Literal["up", "down"]
    # A fixed set of reasons, not free text, so feedback cannot carry email content.
    reason: Literal["incorrect", "not_helpful", "missing_sources", "other"] | None = None


class FeedbackOut(BaseModel):
    status: Literal["recorded"] = "recorded"


class RequestStatusOut(BaseModel):
    request_id: str
    status: Literal["running", "complete", "failed", "cancelled"]
    created_at: datetime
