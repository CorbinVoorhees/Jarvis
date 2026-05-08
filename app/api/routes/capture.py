import json
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from openai import OpenAIError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_capture_service
from app.core.exceptions import UpstreamParseError
from app.schemas.capture import CaptureCreateRequest, CaptureRead
from app.services.capture_service import CaptureService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["captures"])

CaptureTypeFilter = Literal["task", "note", "question"]


@router.post(
    "/capture",
    response_model=CaptureRead,
    status_code=201,
)
def create_capture(
    body: CaptureCreateRequest,
    service: Annotated[CaptureService, Depends(get_capture_service)],
):
    try:
        return service.create_from_raw(body.raw)
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
    except SQLAlchemyError:
        logger.exception("Database error during capture save")
        raise HTTPException(status_code=500, detail="Database error") from None


@router.get("/captures", response_model=list[CaptureRead])
def list_captures(
    service: Annotated[CaptureService, Depends(get_capture_service)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    capture_type: CaptureTypeFilter | None = Query(default=None, alias="type"),
):
    try:
        return service.list_captures(limit=limit, offset=offset, type_filter=capture_type)
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
