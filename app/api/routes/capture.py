import json
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from openai import OpenAIError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_capture_service
from app.core.exceptions import (
    CaptureUpdateInvariantViolation,
    ExternalIdConflictError,
    UpstreamParseError,
)
from app.enums import CaptureSource, CaptureStatus
from app.schemas.capture import (
    CaptureCreateRequest,
    CaptureIngestResponse,
    CapturePatchRequest,
    CaptureRead,
    CaptureStatusUpdateRequest,
)
from app.services.capture_service import CaptureService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["captures"])

CaptureTypeFilter = Literal["task", "note", "question"]


@router.post(
    "/capture",
    response_model=CaptureIngestResponse,
)
def create_capture(
    response: Response,
    body: CaptureCreateRequest,
    service: Annotated[CaptureService, Depends(get_capture_service)],
):
    try:
        result = service.ingest(body)
    except ValidationError as e:
        logger.warning("Capture validation failed: %s", e)
        raise HTTPException(status_code=422, detail=e.errors()) from e
    except UpstreamParseError as e:
        logger.warning("Upstream parse service returned unusable output: %s", e)
        raise HTTPException(status_code=502, detail="Upstream parse service failed") from None
    except json.JSONDecodeError as e:
        logger.warning("Malformed JSON from upstream parse service: %s", e)
        raise HTTPException(status_code=502, detail="Upstream parse service failed") from None
    except ValueError as e:
        logger.warning("Capture parse error: %s", e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        logger.error("Capture configuration error: %s", e)
        raise HTTPException(status_code=500, detail="Service configuration error") from None
    except OpenAIError:
        logger.exception("OpenAI error during capture")
        raise HTTPException(status_code=502, detail="Upstream parse service failed") from None
    except ExternalIdConflictError:
        logger.warning(
            "external_id uniqueness conflict source=%s",
            body.source.value if body.source is not None else CaptureSource.API.value,
        )
        raise HTTPException(
            status_code=409,
            detail="Duplicate external_id for this source",
        ) from None
    except SQLAlchemyError:
        logger.exception("Database error during capture save")
        raise HTTPException(status_code=500, detail="Database error") from None

    response.status_code = 200 if result.duplicate else 201
    return result


@router.get("/captures", response_model=list[CaptureRead])
def list_captures(
    service: Annotated[CaptureService, Depends(get_capture_service)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    capture_type: CaptureTypeFilter | None = Query(default=None, alias="type"),
    capture_status: CaptureStatus | None = Query(default=None, alias="status"),
):
    try:
        return service.list_captures(
            limit=limit,
            offset=offset,
            type_filter=capture_type,
            status_filter=capture_status.value if capture_status is not None else None,
        )
    except SQLAlchemyError:
        logger.exception("Database error during capture list")
        raise HTTPException(status_code=500, detail="Database error") from None


@router.get("/captures/{capture_id}", response_model=CaptureRead)
def get_capture(
    capture_id: int,
    service: Annotated[CaptureService, Depends(get_capture_service)],
):
    try:
        row = service.get_capture(capture_id)
    except SQLAlchemyError:
        logger.exception("Database error during capture retrieve id=%s", capture_id)
        raise HTTPException(status_code=500, detail="Database error") from None
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.patch("/captures/{capture_id}/status", response_model=CaptureRead)
def patch_capture_status(
    capture_id: int,
    body: CaptureStatusUpdateRequest,
    service: Annotated[CaptureService, Depends(get_capture_service)],
):
    try:
        updated = service.update_capture_status(capture_id, body.status)
    except SQLAlchemyError:
        logger.exception("Database error during capture status update id=%s", capture_id)
        raise HTTPException(status_code=500, detail="Database error") from None
    if updated is None:
        raise HTTPException(status_code=404, detail="Not found")
    return updated


@router.patch("/captures/{capture_id}", response_model=CaptureRead)
def patch_capture(
    capture_id: int,
    body: CapturePatchRequest,
    service: Annotated[CaptureService, Depends(get_capture_service)],
):
    try:
        updated = service.patch_capture(capture_id, body)
    except CaptureUpdateInvariantViolation as exc:
        logger.exception(
            "Capture patch invariant violation id=%s invalid_keys=%s",
            capture_id,
            sorted(exc.invalid_keys),
        )
        raise HTTPException(status_code=500, detail="Internal server error") from None
    except ValueError as e:
        logger.warning("Invalid capture edit id=%s: %s", capture_id, e)
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SQLAlchemyError:
        logger.exception("Database error during capture patch id=%s", capture_id)
        raise HTTPException(status_code=500, detail="Database error") from None
    if updated is None:
        raise HTTPException(status_code=404, detail="Not found")
    return updated
