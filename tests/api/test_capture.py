import pytest
from sqlalchemy.exc import OperationalError

import app.repositories.capture_repository as capture_repository_module
from app.core.exceptions import CaptureUpdateInvariantViolation
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
    assert data["duplicate"] is False
    cap = data["capture"]
    assert cap["id"] >= 1
    assert cap["type"] == "task"
    assert cap["title"] == "Buy milk"
    assert cap["raw"] == "Buy milk today"
    assert cap["source"] == "api"
    assert cap["external_id"] is None
    assert cap["status"] == "inbox"
    assert "created_at" in cap
    assert "updated_at" in cap
    assert cap["updated_at"] == cap["created_at"]


def test_new_capture_defaults_to_inbox(client, mock_openai_parse):
    response = client.post("/capture", json={"raw": "Reminder"})
    assert response.status_code == 201
    assert response.json()["capture"]["status"] == "inbox"


def test_get_capture_by_id(client, mock_openai_parse):
    create = client.post("/capture", json={"raw": "Pick something"})
    cid = create.json()["capture"]["id"]
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


def test_list_captures_status_filter(client, mock_openai_parse):
    created = client.post("/capture", json={"raw": "one"})
    cid = created.json()["capture"]["id"]
    client.patch(f"/captures/{cid}/status", json={"status": "processed"})
    client.post("/capture", json={"raw": "two"})
    inbox_rows = client.get("/captures", params={"status": "inbox"})
    assert inbox_rows.status_code == 200
    assert len(inbox_rows.json()) == 1
    processed_rows = client.get("/captures", params={"status": "processed"})
    assert len(processed_rows.json()) == 1


def test_list_captures_combined_type_and_status_filter(client, monkeypatch):
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
    t1 = client.post("/capture", json={"raw": "task a"}).json()
    n1 = client.post("/capture", json={"raw": "NOTE x"}).json()
    client.patch(f"/captures/{t1['capture']['id']}/status", json={"status": "processed"})
    client.patch(f"/captures/{n1['capture']['id']}/status", json={"status": "inbox"})
    combined = client.get("/captures", params={"type": "task", "status": "inbox"})
    assert combined.status_code == 200
    assert len(combined.json()) == 0
    notes_inbox = client.get("/captures", params={"type": "note", "status": "inbox"})
    assert len(notes_inbox.json()) == 1


def test_patch_capture_status_success(client, mock_openai_parse):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]
    resp = client.patch(f"/captures/{cid}/status", json={"status": "processed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processed"
    assert body["id"] == cid


def test_patch_capture_status_invalid_returns_422(client):
    resp = client.patch("/captures/999999/status", json={"status": "not-a-status"})
    assert resp.status_code == 422


def test_patch_capture_status_database_failure_returns_500(client, mock_openai_parse, monkeypatch):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]

    def boom(*args, **kwargs):
        raise OperationalError("UPDATE", {}, Exception("db"))

    monkeypatch.setattr(CaptureRepository, "update_status", boom)
    resp = client.patch(f"/captures/{cid}/status", json={"status": "processed"})
    assert resp.status_code == 500


def test_patch_capture_status_missing_returns_404(client):
    resp = client.patch("/captures/999999/status", json={"status": "processed"})
    assert resp.status_code == 404


def test_patch_capture_partial_update_keeps_unset_fields(client, mock_openai_parse):
    create = client.post("/capture", json={"raw": "Buy milk"})
    cid = create.json()["capture"]["id"]
    patched = client.patch(f"/captures/{cid}", json={"status": "processed"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["title"] == "Buy milk"
    assert body["raw"] == "Buy milk"
    assert body["type"] == "task"
    assert body["status"] == "processed"


def test_patch_capture_explicit_null_clears_time(client, monkeypatch):
    def parser(raw_text: str, client=None):
        return ParsedCapture(
            type="task",
            title="Buy milk",
            content=None,
            question=None,
            time="Friday at 2pm",
            raw=raw_text,
        )

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        parser,
    )
    cid = client.post("/capture", json={"raw": "Reminder"}).json()["capture"]["id"]
    assert client.get(f"/captures/{cid}").json()["time"] == "Friday at 2pm"
    cleared = client.patch(f"/captures/{cid}", json={"time": None})
    assert cleared.status_code == 200
    assert cleared.json()["time"] is None


def test_patch_capture_invalid_type_returns_422(client, mock_openai_parse):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]
    resp = client.patch(f"/captures/{cid}", json={"type": "not-valid"})
    assert resp.status_code == 422


def test_patch_capture_invalid_status_returns_422(client, mock_openai_parse):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]
    resp = client.patch(f"/captures/{cid}", json={"status": "unknown"})
    assert resp.status_code == 422


def test_patch_capture_contradictory_task_question_returns_422(client, mock_openai_parse):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]
    resp = client.patch(
        f"/captures/{cid}",
        json={"type": "task", "title": "T", "question": "oops?"},
    )
    assert resp.status_code == 422


def test_patch_capture_missing_returns_404(client):
    assert client.patch("/captures/999999", json={"title": "Nope"}).status_code == 404


def test_patch_capture_note_to_question_requires_explicit_clears(client, monkeypatch):
    def parser(raw_text: str, client=None):
        return ParsedCapture(
            type="note",
            title=None,
            content="note body",
            question=None,
            time=None,
            raw=raw_text,
        )

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        parser,
    )
    cid = client.post("/capture", json={"raw": "NOTE body"}).json()["capture"]["id"]
    bad = client.patch(
        f"/captures/{cid}",
        json={"type": "question", "question": "Why?"},
    )
    assert bad.status_code == 422

    ok = client.patch(
        f"/captures/{cid}",
        json={
            "type": "question",
            "question": "Why?",
            "content": None,
            "title": None,
        },
    )
    assert ok.status_code == 200
    out = ok.json()
    assert out["type"] == "question"
    assert out["question"] == "Why?"
    assert out["content"] is None
    assert out["title"] is None


def test_patch_capture_forbidden_extra_field_returns_422(client, mock_openai_parse):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]
    resp = client.patch(f"/captures/{cid}", json={"title": "Renamed", "raw": "changed"})
    assert resp.status_code == 422


def test_patch_capture_no_op_does_not_advance_updated_at(client, mock_openai_parse):
    """Echo PATCH exercises merge logic without DB writes.

    Timestamp equality below compares CaptureRead API strings (second resolution only),
    not microsecond equality against stored DB values.
    """
    cid = client.post("/capture", json={"raw": "hello"}).json()["capture"]["id"]
    before = client.get(f"/captures/{cid}").json()
    echo = {
        "type": before["type"],
        "title": before["title"],
        "content": before["content"],
        "question": before["question"],
        "time": before["time"],
        "status": before["status"],
    }
    after = client.patch(f"/captures/{cid}", json=echo)
    assert after.status_code == 200
    body = after.json()
    assert body["title"] == before["title"]
    assert body["updated_at"] == before["updated_at"]


def test_patch_capture_keeps_id_source_created_at_raw(client, mock_openai_parse):
    create = client.post("/capture", json={"raw": "original text"})
    cid = create.json()["capture"]["id"]
    before = client.get(f"/captures/{cid}").json()
    after = client.patch(f"/captures/{cid}", json={"title": "Adjusted title"}).json()
    assert after["title"] == "Adjusted title"
    assert after["id"] == before["id"]
    assert after["source"] == before["source"]
    assert after["raw"] == before["raw"]
    assert after["created_at"] == before["created_at"]


def test_patch_capture_database_failure_returns_500(client, mock_openai_parse, monkeypatch):
    cid = client.post("/capture", json={"raw": "x"}).json()["capture"]["id"]

    def apply_field_updates_flush_fail(self, row, updates):
        """Mirror apply_field_updates pre-flush work, then simulate flush-level DB failure."""
        if not updates:
            return
        bad = set(updates) - capture_repository_module._CAPTURE_PATCHABLE_COLUMNS
        if bad:
            raise CaptureUpdateInvariantViolation(bad)
        for key, value in updates.items():
            setattr(row, key, value)
        raise OperationalError("UPDATE", {}, Exception("db"))

    monkeypatch.setattr(CaptureRepository, "apply_field_updates", apply_field_updates_flush_fail)
    resp = client.patch(f"/captures/{cid}", json={"title": "Different"})
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Database error"


def test_list_captures_invalid_status_query_returns_422(client):
    resp = client.get("/captures", params={"status": "bogus"})
    assert resp.status_code == 422


def test_duplicate_ingestion_returns_200_normalized_raw(client, mock_openai_parse):
    first = client.post("/capture", json={"raw": "Hello    WORLD"})
    assert first.status_code == 201
    p = first.json()
    assert p["duplicate"] is False
    cid = p["capture"]["id"]
    dup = client.post("/capture", json={"raw": "  hello world  "})
    assert dup.status_code == 200
    q = dup.json()
    assert q["duplicate"] is True
    assert q["capture"]["id"] == cid


def test_duplicate_submit_does_not_add_second_row(client, mock_openai_parse, monkeypatch):
    monkeypatch.setattr(
        "app.services.capture_service.DUPLICATE_INGEST_WINDOW_SECONDS",
        3600,
    )
    first = client.post("/capture", json={"raw": "solo message"})
    assert first.status_code == 201
    n1 = len(client.get("/captures").json())
    dup = client.post("/capture", json={"raw": "SOLO MESSAGE"})
    assert dup.status_code == 200
    assert dup.json()["duplicate"] is True
    n2 = len(client.get("/captures").json())
    assert n1 == n2 == 1


def test_duplicate_skips_openai_via_service_monkeypatch(client, monkeypatch):
    calls: list[str] = []

    def fake(raw_text: str, client_api=None):
        calls.append(raw_text)
        return ParsedCapture(
            type="task",
            title="stub",
            content=None,
            question=None,
            time=None,
            raw=raw_text,
        )

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        fake,
    )
    monkeypatch.setattr(
        "app.services.capture_service.DUPLICATE_INGEST_WINDOW_SECONDS",
        3600,
    )
    client.post("/capture", json={"raw": "tracked"})
    client.post("/capture", json={"raw": "Tracked"})
    assert len(calls) == 1


def test_capture_ingestion_invalid_source_returns_422(client, mock_openai_parse):
    resp = client.post("/capture", json={"raw": "hi", "source": "mars"})
    assert resp.status_code == 422


def test_deduplication_scope_by_source(client, mock_openai_parse):
    a = client.post("/capture", json={"raw": "same body"})
    b = client.post("/capture", json={"raw": "same body", "source": "manual"})
    assert a.status_code == 201 and b.status_code == 201
    assert a.json()["capture"]["id"] != b.json()["capture"]["id"]


def test_capture_ingestion_rejects_unknown_body_fields_returns_422(client, mock_openai_parse):
    resp = client.post(
        "/capture",
        json={"raw": "unique extra field rejection", "normalized_raw_hash": "a" * 64},
    )
    assert resp.status_code == 422


def test_external_id_conflict_returns_409(client, mock_openai_parse):
    r1 = client.post("/capture", json={"raw": "first body xyz", "external_id": "ext-a"})
    assert r1.status_code == 201
    r2 = client.post("/capture", json={"raw": "other body zzz completely", "external_id": "ext-a"})
    assert r2.status_code == 409


def test_duplicate_replay_same_raw_and_external_id_returns_200_not_409(client, monkeypatch):
    """Hash+source duplicate check runs before insert; replay does not hit unique index."""

    def fake_parse(raw_text: str, client_api=None):
        return ParsedCapture(
            type="task",
            title="replay",
            content=None,
            question=None,
            time=None,
            raw=raw_text,
        )

    monkeypatch.setattr(
        "app.services.capture_service.parse_capture_with_openai",
        fake_parse,
    )
    monkeypatch.setattr(
        "app.services.capture_service.DUPLICATE_INGEST_WINDOW_SECONDS",
        3600,
    )
    body_text = "ext replay precedence body"
    eid = "stable-external-ref"
    r1 = client.post("/capture", json={"raw": body_text, "external_id": eid})
    assert r1.status_code == 201
    p1 = r1.json()
    r2 = client.post("/capture", json={"raw": body_text, "external_id": eid})
    assert r2.status_code == 200
    p2 = r2.json()
    assert p2["duplicate"] is True
    assert p2["capture"]["id"] == p1["capture"]["id"]


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
