import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.enums import CaptureStatus
from app.integrations.openai_capture import parse_capture_with_openai
from app.repositories.capture_repository import CaptureRepository
from app.schemas.capture import CaptureRead, ParsedCapture

logger = logging.getLogger(__name__)


class CaptureService:
    def __init__(self, db: Session):
        self._db = db
        self._repo = CaptureRepository(db)

    def create_from_raw(self, raw_text: str) -> CaptureRead:
        parsed = parse_capture_with_openai(raw_text)
        return self._persist_parsed(parsed)

    def create_from_parsed(self, parsed: ParsedCapture) -> CaptureRead:
        """Used when OpenAI is mocked in tests."""
        return self._persist_parsed(parsed)

    def _persist_parsed(self, parsed: ParsedCapture) -> CaptureRead:
        try:
            row = self._repo.create(
                type=parsed.type,
                title=parsed.title,
                content=parsed.content,
                question=parsed.question,
                time=parsed.time,
                raw=parsed.raw,
                source="api",
            )
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            logger.exception("Database error while saving capture")
            raise

        logger.info("Capture saved id=%s type=%s", row.id, row.type)
        return CaptureRead.model_validate(row)

    def list_captures(
        self,
        *,
        limit: int,
        offset: int,
        type_filter: str | None = None,
        status_filter: str | None = None,
    ) -> list[CaptureRead]:
        rows = self._repo.list_captures(
            limit=limit,
            offset=offset,
            type_filter=type_filter,
            status_filter=status_filter,
        )
        logger.info(
            "Listed captures limit=%s offset=%s type_filter=%s status_filter=%s count=%s",
            limit,
            offset,
            type_filter,
            status_filter,
            len(rows),
        )
        return [CaptureRead.model_validate(r) for r in rows]

    def get_capture(self, capture_id: int) -> CaptureRead | None:
        row = self._repo.get_by_id(capture_id)
        if row:
            logger.info("Retrieved capture id=%s", capture_id)
        else:
            logger.info("Capture not found id=%s", capture_id)
        return CaptureRead.model_validate(row) if row else None

    def update_capture_status(
        self,
        capture_id: int,
        new_status: CaptureStatus,
    ) -> CaptureRead | None:
        try:
            outcome = self._repo.update_status(capture_id, new_status.value)
            if outcome is None:
                return None
            row, old_status = outcome
            if old_status != new_status.value:
                self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            logger.exception("Database error while updating capture status id=%s", capture_id)
            raise

        if old_status != new_status.value:
            logger.info(
                "Capture %s status changed %s → %s",
                capture_id,
                old_status,
                new_status.value,
            )
        return CaptureRead.model_validate(row)
