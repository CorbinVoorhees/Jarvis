from datetime import datetime, timedelta, timezone

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

    def find_recent_duplicate_by_hash_and_source(
        self,
        *,
        source: str,
        normalized_raw_hash: str,
        window_seconds: int,
        as_of_utc: datetime | None = None,
    ) -> Capture | None:
        """Most recent duplicate within the window.

        Param ``as_of_utc`` anchors the window exclusively for deterministic tests (UTC).

        The cutoff uses application-server UTC clock; Postgres ``created_at`` uses DB time—a
        60s window tolerates modest clock skew between hosts.
        """
        anchor = as_of_utc if as_of_utc is not None else datetime.now(timezone.utc)
        cutoff = anchor - timedelta(seconds=window_seconds)
        stmt: Select[tuple[Capture]] = (
            select(Capture)
            .where(Capture.source == source)
            .where(Capture.normalized_raw_hash == normalized_raw_hash)
            .where(Capture.created_at >= cutoff)
            .order_by(Capture.created_at.desc(), Capture.id.desc())
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
