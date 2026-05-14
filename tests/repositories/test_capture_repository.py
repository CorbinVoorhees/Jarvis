import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import CaptureUpdateInvariantViolation
from app.ingestion.dedup import normalized_raw_sha256_hex
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
        normalized_raw_hash=normalized_raw_sha256_hex("r"),
    )
    db_session.commit()

    repo2 = CaptureRepository(db_session)
    out = repo2.update_status(row.id, "processed")
    assert out is not None
    _updated, old = out
    assert old == "inbox"
    db_session.commit()

    assert repo2.get_by_id(row.id).status == "processed"


def test_repository_apply_field_updates_persists_columns(db_session: Session):
    repo = CaptureRepository(db_session)
    row = repo.create(
        type="task",
        title="x",
        content=None,
        question=None,
        time="later",
        raw="r",
        source="api",
        normalized_raw_hash=normalized_raw_sha256_hex("r"),
    )
    db_session.commit()

    repo.apply_field_updates(
        row,
        {"title": "y", "time": None, "status": "processed"},
    )
    db_session.commit()

    r2 = CaptureRepository(db_session)
    fetched = r2.get_by_id(row.id)
    assert fetched.title == "y"
    assert fetched.time is None
    assert fetched.status == "processed"


def test_repository_apply_field_updates_rejects_immutable_keys(db_session: Session):
    repo = CaptureRepository(db_session)
    row = repo.create(
        type="task",
        title="x",
        content=None,
        question=None,
        time=None,
        raw="r",
        source="api",
        normalized_raw_hash=normalized_raw_sha256_hex("r"),
    )
    db_session.commit()
    with pytest.raises(CaptureUpdateInvariantViolation) as excinfo:
        repo.apply_field_updates(row, {"title": "ok", "raw": "nope"})
    assert "raw" in excinfo.value.invalid_keys


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
        normalized_raw_hash=normalized_raw_sha256_hex("a"),
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
        normalized_raw_hash=normalized_raw_sha256_hex("b"),
    )
    db_session.commit()

    r2 = CaptureRepository(db_session)
    rows = r2.list_captures(limit=10, offset=0, status_filter="inbox", type_filter=None)
    assert len(rows) == 1
    assert rows[0].id == second.id


def test_find_recent_duplicate_matches_within_window(db_session: Session):
    repo = CaptureRepository(db_session)
    h = normalized_raw_sha256_hex("hello world")
    row = repo.create(
        type="task",
        title="t",
        content=None,
        question=None,
        time=None,
        raw="HELLO    world ",
        normalized_raw_hash=h,
    )
    db_session.commit()

    r2 = CaptureRepository(db_session)
    dup = r2.find_recent_duplicate_by_hash_and_source(
        source="api",
        normalized_raw_hash=h,
        window_seconds=3600,
    )
    assert dup is not None
    assert dup.id == row.id


def test_find_recent_duplicate_misses_when_older_than_window(db_session: Session):
    repo = CaptureRepository(db_session)
    h = normalized_raw_sha256_hex("past")
    repo.create(
        type="task",
        title="x",
        content=None,
        question=None,
        time=None,
        raw="past",
        normalized_raw_hash=h,
    )
    db_session.commit()
    db_session.execute(text("UPDATE captures SET created_at = created_at - interval '120 seconds'"))
    db_session.commit()

    r2 = CaptureRepository(db_session)
    dup = r2.find_recent_duplicate_by_hash_and_source(
        source="api",
        normalized_raw_hash=h,
        window_seconds=60,
    )
    assert dup is None


def test_source_external_id_unique_constraint(db_session: Session):
    from sqlalchemy.exc import IntegrityError

    # Duplicate (source, external_id): IntegrityError from Postgres flush inside create();
    # no separate session.flush() needed after create().
    repo = CaptureRepository(db_session)
    h1 = normalized_raw_sha256_hex("first")
    h2 = normalized_raw_sha256_hex("second")
    repo.create(
        type="task",
        title="one",
        content=None,
        question=None,
        time=None,
        raw="first",
        source="api",
        normalized_raw_hash=h1,
        external_id="ext-unique",
    )
    db_session.commit()
    repo2 = CaptureRepository(db_session)
    with pytest.raises(IntegrityError) as excinfo:
        repo2.create(
            type="task",
            title="two",
            content=None,
            question=None,
            time=None,
            raw="second",
            source="api",
            normalized_raw_hash=h2,
            external_id="ext-unique",
        )
    assert "uq_captures_source_external_id" in str(excinfo.value.orig)


def test_duplicate_external_allowed_across_sources(db_session: Session):
    repo = CaptureRepository(db_session)
    h = normalized_raw_sha256_hex("same-ext")
    repo.create(
        type="task",
        title="a",
        content=None,
        question=None,
        time=None,
        raw="same-ext",
        source="api",
        normalized_raw_hash=h,
        external_id="sid-shared",
    )
    repo.create(
        type="task",
        title="b",
        content=None,
        question=None,
        time=None,
        raw="same-ext",
        source="sms",
        normalized_raw_hash=h,
        external_id="sid-shared",
    )
    db_session.commit()
