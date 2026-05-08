import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.repositories.capture_repository import CaptureRepository
from app.schemas.capture import ParsedCapture
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
