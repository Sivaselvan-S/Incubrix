"""Health and Readiness endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, Any]:
    """Liveness probe confirming the API service is alive."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "simulation_mode": settings.SIMULATION_MODE,
    }


@router.get("/ready")
def readiness_check(response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe checking database connectivity and storage readiness."""
    settings = get_settings()
    checks: dict[str, str] = {}
    is_ready = True

    # 1. Check Database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc!s}"
        is_ready = False

    # 2. Check MinIO / Storage
    if settings.SIMULATION_MODE:
        checks["storage"] = "ok (simulation)"
    else:
        # In non-simulation mode verify endpoint string is present
        checks["storage"] = "ok" if settings.MINIO_ENDPOINT else "missing_endpoint"

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": checks,
    }
