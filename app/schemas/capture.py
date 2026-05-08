from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, model_validator


class ParsedCapture(BaseModel):
    """Validated capture produced by the parser. Source of truth for cross-field rules."""

    model_config = {"extra": "forbid"}

    type: Literal["task", "note", "question"]
    title: str | None = None
    content: str | None = None
    question: str | None = None
    time: str | None = None
    raw: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_fields_by_type(self):
        if self.type == "task" and not (self.title and self.title.strip()):
            raise ValueError("title is required for task captures")
        if self.type == "note" and not (self.content and self.content.strip()):
            raise ValueError("content is required for note captures")
        if self.type == "question" and not (self.question and self.question.strip()):
            raise ValueError("question is required for question captures")
        return self


class CaptureCreateRequest(BaseModel):
    raw: str = Field(..., min_length=1)


class CaptureRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    type: str
    title: str | None
    content: str | None
    question: str | None
    time: str | None
    raw: str
    source: str
    created_at: datetime

    @field_serializer("created_at")
    def created_at_utc_z(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
