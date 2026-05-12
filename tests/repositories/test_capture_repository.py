import pytest
from sqlalchemy.orm import Session

from app.repositories.capture_repository import CaptureRepository

pytestmark = pytest.mark.usefixtures("prepare_database", "clean_captures_table")


@pytest.fixture
def db_session():
    from app.db.session import get_session_factory

    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_repository_update_status_persists(db_session: Session):
    repo = CaptureRepository(db_session)
    row = repo.create(
        type="task",
        title="x",
        content=None,
        question=None,
        time=None,
        raw="r",
        source="api",
    )
    db_session.commit()

    repo2 = CaptureRepository(db_session)
    out = repo2.update_status(row.id, "processed")
    assert out is not None
    _updated, old = out
    assert old == "inbox"
    db_session.commit()

    assert repo2.get_by_id(row.id).status == "processed"


def test_repository_list_captures_filters_by_status(db_session: Session):
    repo = CaptureRepository(db_session)
    first = repo.create(
        type="task",
        title="a",
        content=None,
        question=None,
        time=None,
        raw="a",
        source="api",
    )
    repo.update_status(first.id, "processed")
    second = repo.create(
        type="task",
        title="b",
        content=None,
        question=None,
        time=None,
        raw="b",
        source="api",
    )
    db_session.commit()

    r2 = CaptureRepository(db_session)
    rows = r2.list_captures(limit=10, offset=0, status_filter="inbox", type_filter=None)
    assert len(rows) == 1
    assert rows[0].id == second.id
