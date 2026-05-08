from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models.capture import Capture


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
    ) -> Capture:
        row = Capture(
            type=type,
            title=title,
            content=content,
            question=question,
            time=time,
            raw=raw,
            source=source,
        )
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row

    def list_captures(
        self,
        *,
        limit: int,
        offset: int,
        type_filter: str | None = None,
    ) -> list[Capture]:
        stmt: Select[tuple[Capture]] = select(Capture).order_by(
            Capture.created_at.desc(),
            Capture.id.desc(),
        )
        if type_filter is not None:
            stmt = stmt.where(Capture.type == type_filter)
        stmt = stmt.limit(limit).offset(offset)
        return list(self._db.scalars(stmt).all())

    def get_by_id(self, capture_id: int) -> Capture | None:
        stmt = select(Capture).where(Capture.id == capture_id)
        return self._db.scalars(stmt).first()
