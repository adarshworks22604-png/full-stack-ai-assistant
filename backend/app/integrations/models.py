"""Approved fields only. extra='ignore' drops anything else an upstream API returns."""

from pydantic import BaseModel, ConfigDict, Field

BUG_ID_RE = r"^BUG-\d{1,8}$"


class BugRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=BUG_ID_RE)
    title: str = Field(max_length=300)
    status: str = Field(max_length=50)
    affected_version: str | None = Field(default=None, max_length=50)
    resolution: str | None = Field(default=None, max_length=2_000)
    product: str = Field(max_length=100)


class DocPassage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str = Field(max_length=100)
    title: str = Field(max_length=300)
    uri: str | None = Field(default=None, max_length=1_000)
    product: str = Field(max_length=100)
    version: str | None = Field(default=None, max_length=50)
    updated_at: str | None = Field(default=None, max_length=40)
    excerpt: str = Field(max_length=2_000)
