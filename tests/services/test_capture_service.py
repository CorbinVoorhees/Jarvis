import logging
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

import app.services.capture_service as capture_service_module
from app.core.exceptions import ExternalIdConflictError
from app.db.session import get_session_factory
from app.enums import CaptureSource, CaptureStatus
from app.repositories.capture_repository import CaptureRepository
from app.schemas.capture import CaptureCreateRequest, CapturePatchRequest, ParsedCapture
from app.services.capture_service import CaptureService

pytestmark = pytest.mark.usefixtures("prepare_database", "clean_captures_table")


@pytest.fixture
def db_session():
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_create_from_parsed_saves_and_returns_read_model(db_session: Session):
    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="task",
        title="Buy milk",
        content=None,
        question=None,
        time=None,
        raw="Buy milk today",
    )
    out = svc.create_from_parsed(parsed)
    assert out.id >= 1
    assert out.type == "task"
    assert out.title == "Buy milk"
    assert out.raw == "Buy milk today"
    assert out.source == "api"
    assert out.created_at is not None
    assert out.status == CaptureStatus.INBOX
    assert out.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") == out.created_at.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert out.external_id is None


def test_status_transition_processed_and_round_trip(db_session: Session):
    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="note",
        title=None,
        content="text",
        question=None,
        time=None,
        raw="text",
    )
    created = svc.create_from_parsed(parsed)
    updated = svc.update_capture_status(created.id, CaptureStatus.PROCESSED)
    assert updated is not None
    assert updated.status == CaptureStatus.PROCESSED

    back = svc.update_capture_status(created.id, CaptureStatus.INBOX)
    assert back is not None
    assert back.status == CaptureStatus.INBOX


def test_update_capture_status_none_when_missing(db_session: Session):
    svc = CaptureService(db_session)
    assert svc.update_capture_status(40404, CaptureStatus.ARCHIVED) is None


def test_updated_at_changes_after_status_change(db_session: Session):
    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="task",
        title="Do",
        content=None,
        question=None,
        time=None,
        raw="Do",
    )
    created = svc.create_from_parsed(parsed)
    before = svc.get_capture(created.id)
    assert before is not None

    time.sleep(0.05)
    svc.update_capture_status(created.id, CaptureStatus.PROCESSED)

    svc_reload = CaptureService(db_session)
    row = svc_reload.get_capture(created.id)
    assert row is not None
    assert row.created_at == before.created_at
    assert row.updated_at > before.updated_at


def test_list_and_status_update_logging_paths_do_not_raise(db_session: Session, caplog):
    caplog.set_level(logging.INFO)

    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="question",
        raw="why",
        title=None,
        content=None,
        time=None,
        question="why",
    )
    created = svc.create_from_parsed(parsed)
    svc.list_captures(limit=10, offset=0, status_filter="inbox", type_filter=None)
    svc.update_capture_status(created.id, CaptureStatus.ARCHIVED)


def test_patch_capture_question_to_task_with_explicit_question_clear(db_session: Session):
    svc = CaptureService(db_session)
    created = svc.create_from_parsed(
        ParsedCapture(
            type="question",
            title=None,
            content=None,
            question="why sky",
            time=None,
            raw="why sky",
        )
    )
    patch = CapturePatchRequest.model_validate(
        {"type": "task", "title": "Research sky", "question": None},
    )
    updated = svc.patch_capture(created.id, patch)
    assert updated is not None
    assert updated.type == "task"
    assert updated.title == "Research sky"
    assert updated.question is None
    assert updated.raw == "why sky"


def test_patch_capture_invalid_edit_raises_without_commit(db_session: Session):
    svc = CaptureService(db_session)
    created = svc.create_from_parsed(
        ParsedCapture(
            type="task",
            title="T",
            content=None,
            question=None,
            time=None,
            raw="task text",
        )
    )
    patch = CapturePatchRequest.model_validate({"question": "not allowed"})
    with pytest.raises(ValueError):
        svc.patch_capture(created.id, patch)


def test_patch_capture_db_failure_rolls_back_after_orm_mutate(db_session: Session, monkeypatch):
    svc = CaptureService(db_session)
    created = svc.create_from_parsed(
        ParsedCapture(
            type="task",
            title="Stable",
            content=None,
            question=None,
            time=None,
            raw="Stable",
        )
    )

    def boom_flush(*_args, **_kwargs):
        raise SQLAlchemyError("simulated flush failure")

    monkeypatch.setattr(db_session, "flush", boom_flush)

    patch = CapturePatchRequest.model_validate({"title": "Changed"})
    with pytest.raises(SQLAlchemyError):
        svc.patch_capture(created.id, patch)

    svc2 = CaptureService(db_session)
    current = svc2.get_capture(created.id)
    assert current is not None
    assert current.title == "Stable"


def test_updated_at_moves_after_capture_field_patch(db_session: Session):
    svc = CaptureService(db_session)
    created = svc.create_from_parsed(
        ParsedCapture(type="task", title="Old", raw="Old", question=None, time=None, content=None)
    )

    time.sleep(0.05)

    svc.patch_capture(created.id, CapturePatchRequest.model_validate({"title": "Renamed"}))

    svc_reload = CaptureService(db_session)
    row = svc_reload.get_capture(created.id)
    assert row is not None
    assert row.title == "Renamed"
    assert row.updated_at > row.created_at


def test_patch_capture_logs_success(monkeypatch, db_session: Session):
    messages: list[str] = []

    def _info(msg, *args):
        messages.append(msg % args if args else msg)

    monkeypatch.setattr(capture_service_module.logger, "info", _info)

    svc = CaptureService(db_session)
    created = svc.create_from_parsed(
        ParsedCapture(type="task", title="A", raw="A", question=None, time=None, content=None)
    )

    svc.patch_capture(
        created.id,
        CapturePatchRequest.model_validate({"title": "B", "time": "soon"}),
    )

    assert any(str(created.id) in entry and "updated fields=" in entry for entry in messages)


def test_db_error_during_save_propagates_after_rollback(db_session: Session, monkeypatch):
    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="note",
        title=None,
        content="A note",
        question=None,
        time=None,
        raw="A note",
    )

    def boom(*args, **kwargs):
        raise SQLAlchemyError("simulated failure")

    monkeypatch.setattr(CaptureRepository, "create", boom)
    with pytest.raises(SQLAlchemyError):
        svc.create_from_parsed(parsed)


def fake_parse_always_task(raw_text: str, client=None):
    return ParsedCapture(
        type="task",
        title="stub",
        content=None,
        question=None,
        time=None,
        raw=raw_text,
    )


def test_ingest_duplicate_skips_openai(monkeypatch, db_session: Session):
    calls: list[str] = []

    def tracking_parse(raw_text: str, client=None):
        calls.append(raw_text)
        return fake_parse_always_task(raw_text, client)

    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", tracking_parse)

    svc = CaptureService(db_session)
    req = CaptureCreateRequest(raw="only once phrase")
    a = svc.ingest(req)
    assert a.duplicate is False
    b = svc.ingest(req)
    assert b.duplicate is True
    assert b.capture.id == a.capture.id
    assert len(calls) == 1


def test_ingest_same_normalized_raw_is_duplicate_even_when_created_at_is_old(
    monkeypatch,
    db_session: Session,
):
    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", fake_parse_always_task)

    svc = CaptureService(db_session)
    req = CaptureCreateRequest(raw="aging payload")
    first = svc.ingest(req)
    assert first.duplicate is False

    db_session.execute(text("UPDATE captures SET created_at = created_at - interval '120 seconds'"))
    db_session.commit()

    svc2 = CaptureService(db_session)
    second = svc2.ingest(req)
    assert second.duplicate is True
    assert second.capture.id == first.capture.id


def test_ingest_unique_hash_integrity_path_returns_duplicate(monkeypatch, db_session: Session):
    parse_calls: list[str] = []

    def tracking_parse(raw_text: str, client=None):
        parse_calls.append(raw_text)
        return fake_parse_always_task(raw_text, client)

    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", tracking_parse)
    svc = CaptureService(db_session)
    req = CaptureCreateRequest(raw="integrity path body")
    first = svc.ingest(req)
    assert first.duplicate is False

    _orig = CaptureRepository.find_by_source_and_normalized_hash

    def spy_find(self, *, source, normalized_raw_hash):
        spy_find.calls += 1
        if spy_find.calls == 1:
            return None
        return _orig(self, source=source, normalized_raw_hash=normalized_raw_hash)

    spy_find.calls = 0
    monkeypatch.setattr(CaptureRepository, "find_by_source_and_normalized_hash", spy_find)

    second = svc.ingest(req)
    assert second.duplicate is True
    assert second.capture.id == first.capture.id
    assert spy_find.calls == 2
    assert len(parse_calls) == 2


def test_external_id_integrity_same_raw_is_duplicate(monkeypatch, db_session: Session):
    """Postgres may report uq_captures_source_external_id for a same-raw replay race."""
    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", fake_parse_always_task)
    svc = CaptureService(db_session)
    body = "external id integrity same raw"
    eid = "ext-race-key"
    first = svc.ingest(CaptureCreateRequest(raw=body, external_id=eid))
    assert first.duplicate is False

    _orig_find = CaptureRepository.find_by_source_and_normalized_hash

    def spy_find(self, *, source, normalized_raw_hash):
        spy_find.calls += 1
        if spy_find.calls == 1:
            return None
        return _orig_find(self, source=source, normalized_raw_hash=normalized_raw_hash)

    spy_find.calls = 0
    monkeypatch.setattr(CaptureRepository, "find_by_source_and_normalized_hash", spy_find)

    class _Diag:
        constraint_name = "uq_captures_source_external_id"

    class _Orig:
        pgcode = "23505"
        diag = _Diag()

    def create_stub(self, **kwargs):
        create_stub.calls += 1
        raise IntegrityError("statement", {}, _Orig())

    create_stub.calls = 0
    monkeypatch.setattr(CaptureRepository, "create", create_stub)

    second = svc.ingest(CaptureCreateRequest(raw=body, external_id=eid))
    assert second.duplicate is True
    assert second.capture.id == first.capture.id
    assert create_stub.calls == 1
    assert spy_find.calls == 1


def test_duplicate_ingest_logs_when_external_id_differs(monkeypatch, db_session: Session, caplog):
    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", fake_parse_always_task)
    caplog.set_level(logging.WARNING)
    svc = CaptureService(db_session)
    svc.ingest(CaptureCreateRequest(raw="shared raw text", external_id="stored-id"))
    svc.ingest(CaptureCreateRequest(raw="shared raw text", external_id="new-id"))
    assert any("Ignoring incoming external_id" in rec.message for rec in caplog.records)


def test_external_id_conflict_raises_external_id_conflict_error(monkeypatch, db_session: Session):
    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", fake_parse_always_task)

    svc = CaptureService(db_session)
    svc.ingest(CaptureCreateRequest(raw="body one wording", external_id="shared-twilio"))
    with pytest.raises(ExternalIdConflictError):
        svc.ingest(CaptureCreateRequest(raw="very different wording", external_id="shared-twilio"))


def test_create_from_parsed_idempotent_on_duplicate_hash(db_session: Session):
    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="task",
        title="t",
        content=None,
        question=None,
        time=None,
        raw="idempotent create_from_parsed raw",
    )
    a = svc.create_from_parsed(parsed)
    b = svc.create_from_parsed(parsed)
    assert a.id == b.id


def test_create_from_parsed_invalid_string_source_raises(db_session: Session):
    svc = CaptureService(db_session)
    parsed = ParsedCapture(
        type="task",
        title="t",
        content=None,
        question=None,
        time=None,
        raw="bogus source test string",
    )
    with pytest.raises(ValueError, match="invalid capture source"):
        svc.create_from_parsed(parsed, source="not-a-real-source")


def test_duplicate_not_detected_across_sources(monkeypatch, db_session: Session):
    monkeypatch.setattr(capture_service_module, "parse_capture_with_openai", fake_parse_always_task)

    svc = CaptureService(db_session)
    api_row = svc.ingest(CaptureCreateRequest(raw="dupe wording"))
    manual_row = svc.ingest(CaptureCreateRequest(raw="dupe wording", source=CaptureSource.MANUAL))
    assert api_row.duplicate is False and manual_row.duplicate is False
    assert manual_row.capture.id != api_row.capture.id
