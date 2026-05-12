import pytest
from pydantic import ValidationError

from app.schemas.capture import CaptureStatusUpdateRequest, ParsedCapture


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
