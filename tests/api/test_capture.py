import pytest
from sqlalchemy.exc import OperationalError

from app.repositories.capture_repository import CaptureRepository
from app.schemas.capture import ParsedCapture

pytestmark = pytest.mark.usefixtures("prepare_database", "clean_captures_table")


@pytest.fixture
def mock_openai_parse(monkeypatch):
    def fake_parse(raw_text: str, client=None):
        return ParsedCapture(
            type="task",
            title="Buy milk",
            content=None,
            question=None,
            time=None,
            raw=raw_text,
        )

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        fake_parse,
    )


def test_post_capture_saves_and_returns_payload(client, mock_openai_parse):
    response = client.post("/capture", json={"raw": "Buy milk today"})
    assert response.status_code == 201
    data = response.json()
    assert data["id"] >= 1
    assert data["type"] == "task"
    assert data["title"] == "Buy milk"
    assert data["raw"] == "Buy milk today"
    assert data["source"] == "api"
    assert "created_at" in data


def test_get_capture_by_id(client, mock_openai_parse):
    create = client.post("/capture", json={"raw": "Pick something"})
    cid = create.json()["id"]
    got = client.get(f"/captures/{cid}")
    assert got.status_code == 200
    assert got.json()["id"] == cid


def test_get_capture_missing_returns_404(client):
    assert client.get("/captures/99999").status_code == 404


def test_list_captures_pagination(client, mock_openai_parse):
    for i in range(3):
        client.post("/capture", json={"raw": f"Task {i}"})
    page1 = client.get("/captures", params={"limit": 2, "offset": 0})
    assert page1.status_code == 200
    assert len(page1.json()) == 2
    page2 = client.get("/captures", params={"limit": 2, "offset": 2})
    assert len(page2.json()) == 1


def test_list_captures_type_filter(client, monkeypatch):
    def parser(raw_text: str, client=None):
        if "NOTE" in raw_text:
            return ParsedCapture(
                type="note",
                title=None,
                content="body",
                question=None,
                time=None,
                raw=raw_text,
            )
        return ParsedCapture(
            type="task",
            title="t",
            content=None,
            question=None,
            time=None,
            raw=raw_text,
        )

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        parser,
    )
    client.post("/capture", json={"raw": "task one"})
    client.post("/capture", json={"raw": "NOTE body"})
    tasks = client.get("/captures", params={"type": "task"})
    notes = client.get("/captures", params={"type": "note"})
    assert len(tasks.json()) == 1
    assert len(notes.json()) == 1


def test_capture_database_failure_returns_500(client, monkeypatch, mock_openai_parse):
    def boom(*args, **kwargs):
        raise OperationalError("INSERT", {}, Exception("db"))

    monkeypatch.setattr(CaptureRepository, "create", boom)
    response = client.post("/capture", json={"raw": "anything"})
    assert response.status_code == 500


def test_openai_failure_returns_502(client, monkeypatch):
    from openai import OpenAIError

    def fail(*args, **kwargs):
        raise OpenAIError("upstream failure")

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        fail,
    )
    response = client.post("/capture", json={"raw": "anything"})
    assert response.status_code == 502


def test_empty_openai_response_returns_502(client, monkeypatch):
    from app.core.exceptions import UpstreamParseError

    def empty_response(*args, **kwargs):
        raise UpstreamParseError("Empty response from upstream parse service")

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        empty_response,
    )
    response = client.post("/capture", json={"raw": "anything"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream parse service failed"


def test_openai_json_failing_parsed_capture_validation_returns_502(client, monkeypatch):
    """JSON from model is valid but fails ParsedCapture rules (task without title)."""

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            class Msg:
                content = (
                    '{"type": "task", "title": null, "content": null, '
                    '"question": null, "time": null, "raw": "ignored"}'
                )

            class Choice:
                message = Msg()

            class Resp:
                choices = [Choice()]

            return Resp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            pass

        chat = FakeChat()

    monkeypatch.setattr("app.integrations.openai_capture.OpenAI", FakeOpenAI)
    response = client.post("/capture", json={"raw": "user said"})
    assert response.status_code == 502
    body = response.json()
    assert body["detail"] == "Upstream parse service failed"
    assert "errors" not in body
