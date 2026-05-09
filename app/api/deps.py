from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.capture_service import CaptureService


def get_capture_service(db: Session = Depends(get_db)) -> CaptureService:
    return CaptureService(db)
