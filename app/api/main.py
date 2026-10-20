"""FastAPI main application entrypoint."""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, preflight
from app.config import get_settings
from app.db.session import init_db
from app.logging import correlation_id_ctx, get_logger, setup_logging
from app.runtime import router as connector_router

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    logger.info("Initializing database schema...")
    init_db()
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Connector service with living, verifiable Passports and Preflight Court.",
    version="1.0.0",
    lifespan=lifespan,
)

# Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Extracts or generates an X-Correlation-Id and binds it to the logging context."""
    corr_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    token = correlation_id_ctx.set(corr_id)
    try:
        response: Response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response
    finally:
        correlation_id_ctx.reset(token)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Formats all HTTP exceptions into the standard error envelope."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    # Wrap non-dictionary messages into the standard contract shape
    error_payload = {
        "error": {
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "retryable": exc.status_code >= 500,
            "details": {"status_code": exc.status_code},
        }
    }
    return JSONResponse(status_code=exc.status_code, content=error_payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles unexpected runtime exceptions gracefully."""
    logger.exception("Unhandled server exception: %s", exc)
    error_payload = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected internal server error occurred.",
            "retryable": True,
            "details": {"error": str(exc)},
        }
    }
    return JSONResponse(status_code=500, content=error_payload)


# Mount core routes
app.include_router(health.router)
app.include_router(preflight.router)
app.include_router(connector_router.router)
