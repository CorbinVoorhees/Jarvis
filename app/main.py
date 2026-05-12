import logging
import sys

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.capture import router as capture_router
from app.api.routes.health import router as health_router
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

app_log = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


@app.exception_handler(RequestValidationError)
async def request_validation_logging_handler(request: Request, exc: RequestValidationError):
    for err in exc.errors():
        loc = tuple(err.get("loc", []))
        err_input = err.get("input")
        if loc == ("body", "status"):
            app_log.warning("Invalid capture status attempt PATCH body input=%s", err_input)
        elif loc == ("query", "status"):
            app_log.warning("Invalid capture status attempt list query input=%s", err_input)
        elif (
            request.url.path.rstrip("/") == "/captures"
            and request.method == "GET"
            and loc == ("query", "type")
        ):
            app_log.warning("Captures list type filter validation rejected input=%s", err_input)

    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/")
def root():
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.app_env,
    }


app.include_router(health_router)
app.include_router(capture_router)
