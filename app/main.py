import logging
import sys

from fastapi import FastAPI

from app.api.routes.capture import router as capture_router
from app.api.routes.health import router as health_router
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

app = FastAPI(title=settings.app_name)


@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env,
    }


app.include_router(health_router)
app.include_router(capture_router)
