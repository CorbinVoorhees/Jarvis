from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env,
    }

app.include_router(health_router)