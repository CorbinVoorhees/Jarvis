from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.enums import CaptureStatus

CaptureTypeLiteral = Literal["task", "note", "question"]


class ParsedCapture(BaseModel):
    """Validated capture produced by the parser. Source of truth for cross-field rules."""

    model_config = {"extra": "forbid"}

    type: CaptureTypeLiteral
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

    @field_validator("raw", mode="before")
    @classmethod
    def strip_raw(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


class CaptureRead(BaseModel):
    """API read model.

    Datetime fields serialize to UTC with second resolution only (no fractional seconds).
    Clients comparing timestamps should treat equality at API-string granularity.
    """

    model_config = {"from_attributes": True}

    id: int
    type: str
    title: str | None
    content: str | None
    question: str | None
    time: str | None
    raw: str
    source: str
    status: CaptureStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at")
    def created_at_utc_z(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_serializer("updated_at")
    def updated_at_utc_z(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CaptureStatusUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    status: CaptureStatus


class CapturePatchRequest(BaseModel):
    """Partial PATCH body.

    Omitted keys are unchanged; explicit null clears nullable fields.
    """

    model_config = {"extra": "forbid"}

    type: CaptureTypeLiteral | None = None
    title: str | None = None
    content: str | None = None
    question: str | None = None
    time: str | None = None
    status: CaptureStatus | None = None

    @model_validator(mode="after")
    def reject_null_type_or_status(self):
        if "type" in self.model_fields_set and self.type is None:
            raise ValueError("type cannot be null")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


def validate_capture_consistency(
    *,
    capture_type: str,
    title: str | None,
    content: str | None,
    question: str | None,
) -> None:
    """Cross-field rules for merged capture state. Raises ValueError on invalid state.

    Tasks may retain non-null content; notes may retain non-null title — both allowed by PRD today.
    """
    if capture_type == "task":
        if not (title and title.strip()):
            raise ValueError("title is required for task captures")
        if question is not None:
            raise ValueError("question must be null for task captures")
        return None
    if capture_type == "note":
        if not (content and content.strip()):
            raise ValueError("content is required for note captures")
        if question is not None:
            raise ValueError("question must be null for note captures")
        return None
    if capture_type == "question":
        if not (question and question.strip()):
            raise ValueError("question is required for question captures")
        if title is not None:
            raise ValueError("title must be null for question captures")
        if content is not None:
            raise ValueError("content must be null for question captures")
        return None
    raise ValueError(f"invalid capture type: {capture_type}")
