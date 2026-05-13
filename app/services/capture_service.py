import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.enums import CaptureStatus
from app.integrations.openai_capture import parse_capture_with_openai
from app.repositories.capture_repository import CaptureRepository
from app.schemas.capture import (
    CapturePatchRequest,
    CaptureRead,
    ParsedCapture,
    validate_capture_consistency,
)

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

    @staticmethod
    def _normalized_patch_text(value: str | None) -> str | None:
        """Strip user strings; blank becomes None."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def patch_capture(self, capture_id: int, patch: CapturePatchRequest) -> CaptureRead | None:
        row = self._repo.get_by_id(capture_id)
        if row is None:
            logger.info("Capture patch: missing capture id=%s", capture_id)
            return None

        if not patch.model_fields_set:
            return CaptureRead.model_validate(row)

        fs = patch.model_fields_set
        merged_type = patch.type if "type" in fs else row.type
        merged_status = patch.status.value if "status" in fs else row.status

        merged_title = row.title
        merged_content = row.content
        merged_question = row.question
        merged_time = row.time
        if "title" in fs:
            merged_title = self._normalized_patch_text(patch.title)
        if "content" in fs:
            merged_content = self._normalized_patch_text(patch.content)
        if "question" in fs:
            merged_question = self._normalized_patch_text(patch.question)
        if "time" in fs:
            merged_time = self._normalized_patch_text(patch.time)

        validate_capture_consistency(
            capture_type=merged_type,
            title=merged_title,
            content=merged_content,
            question=merged_question,
        )

        updates: dict[str, object] = {}
        if merged_type != row.type:
            updates["type"] = merged_type
        if merged_title != row.title:
            updates["title"] = merged_title
        if merged_content != row.content:
            updates["content"] = merged_content
        if merged_question != row.question:
            updates["question"] = merged_question
        if merged_time != row.time:
            updates["time"] = merged_time
        if merged_status != row.status:
            updates["status"] = merged_status

        if not updates:
            return CaptureRead.model_validate(row)

        try:
            self._repo.apply_field_updates(row, updates)
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            logger.exception("Database error while patching capture id=%s", capture_id)
            raise

        logger.info(
            "Capture %s updated fields=%s",
            capture_id,
            ",".join(sorted(updates.keys())),
        )
        return CaptureRead.model_validate(row)

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
