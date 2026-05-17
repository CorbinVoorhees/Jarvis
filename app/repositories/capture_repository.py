from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import CaptureUpdateInvariantViolation
from app.db.models.capture import Capture

_CAPTURE_PATCHABLE_COLUMNS = frozenset(
    {"type", "title", "content", "question", "time", "status"},
)


class CaptureRepository:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        type: str,
        title: str | None,
        content: str | None,
        question: str | None,
        time: str | None,
        raw: str,
        source: str = "api",
        normalized_raw_hash: str,
        external_id: str | None = None,
    ) -> Capture:
        row = Capture(
            type=type,
            title=title,
            content=content,
            question=question,
            time=time,
            raw=raw,
            source=source,
            normalized_raw_hash=normalized_raw_hash,
            external_id=external_id,
        )
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row

    def find_by_source_and_normalized_hash(
        self,
        *,
        source: str,
        normalized_raw_hash: str,
    ) -> Capture | None:
        """Return the capture for this source + normalized hash (unique at DB level)."""
        stmt: Select[tuple[Capture]] = (
            select(Capture)
            .where(Capture.source == source)
            .where(Capture.normalized_raw_hash == normalized_raw_hash)
            .limit(1)
        )
        return self._db.scalars(stmt).first()

    def find_by_source_and_external_id(
        self,
        *,
        source: str,
        external_id: str,
    ) -> Capture | None:
        """Return the row for (source, external_id); partial unique index allows only one."""
        stmt: Select[tuple[Capture]] = (
            select(Capture)
            .where(Capture.source == source)
            .where(Capture.external_id == external_id)
            .limit(1)
        )
        return self._db.scalars(stmt).first()

    def list_captures(
        self,
        *,
        limit: int,
        offset: int,
        type_filter: str | None = None,
        status_filter: str | None = None,
    ) -> list[Capture]:
        stmt: Select[tuple[Capture]] = select(Capture).order_by(
            Capture.created_at.desc(),
            Capture.id.desc(),
        )
        if type_filter is not None:
            stmt = stmt.where(Capture.type == type_filter)
        if status_filter is not None:
            stmt = stmt.where(Capture.status == status_filter)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._db.scalars(stmt).all())

    def get_by_id(self, capture_id: int) -> Capture | None:
        stmt = select(Capture).where(Capture.id == capture_id)
        return self._db.scalars(stmt).first()

    def apply_field_updates(self, row: Capture, updates: dict[str, object]) -> None:
        """Apply in-place updates. Caller commits when appropriate."""
        if not updates:
            return
        bad = set(updates) - _CAPTURE_PATCHABLE_COLUMNS
        if bad:
            raise CaptureUpdateInvariantViolation(bad)
        for key, value in updates.items():
            setattr(row, key, value)
        self._db.flush()
        self._db.refresh(row)

    def update_status(self, capture_id: int, status: str) -> tuple[Capture, str] | None:
        row = self.get_by_id(capture_id)
        if row is None:
            return None
        old_status = row.status
        if old_status == status:
            return (row, old_status)
        row.status = status
        self._db.flush()
        self._db.refresh(row)
        return (row, old_status)
