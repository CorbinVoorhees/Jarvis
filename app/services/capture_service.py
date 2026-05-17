import logging

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateRawHashConflictError, ExternalIdConflictError
from app.enums import CaptureSource, CaptureStatus
from app.ingestion.dedup import normalized_raw_sha256_hex
from app.integrations.openai_capture import parse_capture_with_openai
from app.repositories.capture_repository import CaptureRepository
from app.schemas.capture import (
    CaptureCreateRequest,
    CaptureIngestResponse,
    CapturePatchRequest,
    CaptureRead,
    ParsedCapture,
    validate_capture_consistency,
)

logger = logging.getLogger(__name__)

_UQ_SOURCE_EXTERNAL_ID_INDEX = "uq_captures_source_external_id"
_UQ_SOURCE_NORMALIZED_HASH_INDEX = "uq_captures_source_normalized_raw_hash"


def _external_id_unique_violation(exc: IntegrityError) -> bool:
    """True when PostgreSQL rejects duplicate (source, external_id) for our partial unique index."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    pgcode = getattr(orig, "pgcode", None)
    diag = getattr(orig, "diag", None)
    if pgcode == "23505":
        constraint = getattr(diag, "constraint_name", None) if diag is not None else None
        if constraint == _UQ_SOURCE_EXTERNAL_ID_INDEX:
            return True
        # Some drivers omit constraint_name; Postgres error detail still names the violated index.
        return _UQ_SOURCE_EXTERNAL_ID_INDEX in str(orig)
    return False


def _source_hash_unique_violation(exc: IntegrityError) -> bool:
    """True when PostgreSQL rejects duplicate (source, normalized_raw_hash)."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    pgcode = getattr(orig, "pgcode", None)
    diag = getattr(orig, "diag", None)
    if pgcode == "23505":
        constraint = getattr(diag, "constraint_name", None) if diag is not None else None
        if constraint == _UQ_SOURCE_NORMALIZED_HASH_INDEX:
            return True
        return _UQ_SOURCE_NORMALIZED_HASH_INDEX in str(orig)
    return False


def _normalized_ingestion_source(source: str | CaptureSource | None) -> str:
    if isinstance(source, CaptureSource):
        return source.value
    if source is None:
        return CaptureSource.API.value
    try:
        return CaptureSource(source).value
    except ValueError:
        allowed = ", ".join(sorted(s.value for s in CaptureSource))
        raise ValueError(f"invalid capture source {source!r}; must be one of: {allowed}") from None


def _log_ignored_external_id_if_needed(
    *,
    source: str,
    stored_external_id: str | None,
    incoming_external_id: str | None,
) -> None:
    if incoming_external_id is None:
        return
    if stored_external_id == incoming_external_id:
        return
    logger.warning(
        "Ignoring incoming external_id=%r for source=%s: duplicate ingest matches existing "
        "capture by normalized raw (stored external_id=%r)",
        incoming_external_id,
        source,
        stored_external_id,
    )


class CaptureService:
    def __init__(self, db: Session):
        self._db = db
        self._repo = CaptureRepository(db)

    def ingest(self, body: CaptureCreateRequest) -> CaptureIngestResponse:
        raw_stripped = body.raw
        source = CaptureSource.API.value if body.source is None else body.source.value
        external_id = body.external_id
        ingest_hash = normalized_raw_sha256_hex(raw_stripped)

        duplicate = self._repo.find_by_source_and_normalized_hash(
            source=source,
            normalized_raw_hash=ingest_hash,
        )
        if duplicate is not None:
            _log_ignored_external_id_if_needed(
                source=source,
                stored_external_id=duplicate.external_id,
                incoming_external_id=external_id,
            )
            cap_read = CaptureRead.model_validate(duplicate)
            logger.info(
                "source=%s duplicate=%s capture_id=%s external_id=%s",
                source,
                str(True).lower(),
                duplicate.id,
                external_id if external_id is not None else "",
            )
            return CaptureIngestResponse(duplicate=True, capture=cap_read)

        parsed = parse_capture_with_openai(raw_stripped)
        try:
            persisted = self._persist_parsed(
                parsed,
                source=source,
                ingest_hash=ingest_hash,
                external_id=external_id,
            )
        except DuplicateRawHashConflictError as dup:
            existing = dup.existing
            _log_ignored_external_id_if_needed(
                source=source,
                stored_external_id=existing.external_id,
                incoming_external_id=external_id,
            )
            cap_read = CaptureRead.model_validate(existing)
            logger.info(
                "source=%s duplicate=%s capture_id=%s external_id=%s",
                source,
                str(True).lower(),
                existing.id,
                external_id if external_id is not None else "",
            )
            return CaptureIngestResponse(duplicate=True, capture=cap_read)

        return CaptureIngestResponse(duplicate=False, capture=persisted)

    def create_from_raw(self, raw_text: str) -> CaptureIngestResponse:
        return self.ingest(CaptureCreateRequest(raw=raw_text))

    def create_from_parsed(
        self,
        parsed: ParsedCapture,
        *,
        source: str | CaptureSource | None = None,
        external_id: str | None = None,
    ) -> CaptureRead:
        """Used when OpenAI is mocked in tests.

        Raises:
            ValueError: If ``source`` is a string that is not a valid CaptureSource value.
        """
        src = _normalized_ingestion_source(source)
        try:
            return self._persist_parsed(parsed, source=src, external_id=external_id)
        except DuplicateRawHashConflictError as dup:
            _log_ignored_external_id_if_needed(
                source=src,
                stored_external_id=dup.existing.external_id,
                incoming_external_id=external_id,
            )
            return CaptureRead.model_validate(dup.existing)

    def _persist_parsed(
        self,
        parsed: ParsedCapture,
        *,
        source: str = CaptureSource.API.value,
        ingest_hash: str | None = None,
        external_id: str | None = None,
    ) -> CaptureRead:
        h = ingest_hash if ingest_hash is not None else normalized_raw_sha256_hex(parsed.raw)
        try:
            row = self._repo.create(
                type=parsed.type,
                title=parsed.title,
                content=parsed.content,
                question=parsed.question,
                time=parsed.time,
                raw=parsed.raw,
                source=source,
                normalized_raw_hash=h,
                external_id=external_id,
            )
            self._db.commit()
        except IntegrityError as e:
            self._db.rollback()
            if _external_id_unique_violation(e) and external_id is not None:
                existing_by_ext = self._repo.find_by_source_and_external_id(
                    source=source,
                    external_id=external_id,
                )
                if existing_by_ext is not None and existing_by_ext.normalized_raw_hash == h:
                    raise DuplicateRawHashConflictError(existing_by_ext) from None
                if existing_by_ext is not None:
                    logger.warning(
                        "external_id uniqueness violation during capture save source=%s",
                        source,
                    )
                    raise ExternalIdConflictError from None
                logger.exception(
                    "external_id uniqueness violation but no matching row source=%s",
                    source,
                )
                raise
            if _source_hash_unique_violation(e):
                existing = self._repo.find_by_source_and_normalized_hash(
                    source=source,
                    normalized_raw_hash=h,
                )
                if existing is None:
                    logger.exception(
                        "normalized_raw_hash uniqueness violation but no row found "
                        "source=%s hash_prefix=%s",
                        source,
                        h[:16],
                    )
                    raise
                raise DuplicateRawHashConflictError(existing) from None
            logger.exception("Database error while saving capture")
            raise
        except SQLAlchemyError:
            self._db.rollback()
            logger.exception("Database error while saving capture")
            raise

        logger.info(
            "source=%s duplicate=%s capture_id=%s external_id=%s",
            source,
            str(False).lower(),
            row.id,
            external_id if external_id is not None else "",
        )
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
