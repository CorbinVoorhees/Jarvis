import pytest
from pydantic import ValidationError

from app.schemas.capture import (
    CaptureCreateRequest,
    CapturePatchRequest,
    CaptureStatusUpdateRequest,
    ParsedCapture,
    validate_capture_consistency,
)


def test_capture_create_request_forbids_extra_fields():
    with pytest.raises(ValidationError):
        CaptureCreateRequest.model_validate({"raw": "hi", "normalized_raw_hash": "a" * 64})


def test_task_requires_non_empty_title():
    with pytest.raises(ValidationError):
        ParsedCapture(type="task", title=None, raw="do something")
    with pytest.raises(ValidationError):
        ParsedCapture(type="task", title="   ", raw="do something")


def test_note_requires_non_empty_content():
    with pytest.raises(ValidationError):
        ParsedCapture(type="note", content=None, raw="remember this")
    with pytest.raises(ValidationError):
        ParsedCapture(type="note", content="", raw="remember this")


def test_question_requires_non_empty_question():
    with pytest.raises(ValidationError):
        ParsedCapture(type="question", question=None, raw="why sky blue")
    with pytest.raises(ValidationError):
        ParsedCapture(type="question", question="  \t", raw="why sky blue")


def test_valid_task():
    p = ParsedCapture(type="task", title="Buy cheese", raw="Add cheese to shopping list")
    assert p.type == "task"
    assert p.title == "Buy cheese"


def test_valid_note():
    p = ParsedCapture(type="note", content="Idea: paint room", raw="Idea: paint room")
    assert p.content == "Idea: paint room"


def test_valid_question():
    p = ParsedCapture(type="question", question="Is it raining?", raw="Is it raining?")
    assert p.question == "Is it raining?"


def test_capture_status_update_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        CaptureStatusUpdateRequest.model_validate({"status": "not-valid"})


def test_capture_patch_rejects_null_type_when_explicit():
    with pytest.raises(ValidationError):
        CapturePatchRequest.model_validate({"type": None})


def test_capture_patch_rejects_null_status_when_explicit():
    with pytest.raises(ValidationError):
        CapturePatchRequest.model_validate({"status": None})


def test_validate_consistency_task_rejects_question():
    with pytest.raises(ValueError):
        validate_capture_consistency(capture_type="task", title="X", content=None, question="Q")


def test_validate_consistency_question_rejects_structured_noise():
    with pytest.raises(ValueError):
        validate_capture_consistency(
            capture_type="question",
            title="T",
            content=None,
            question="Q?",
        )
