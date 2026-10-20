from fastapi import Header, HTTPException

from app.db.session import get_db

__all__ = ["get_db", "require_idempotency_key"]


def require_idempotency_key(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str:
    """Enforces that POST requests must provide an Idempotency-Key header."""
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Header 'Idempotency-Key' is required on this endpoint.",
                    "retryable": False,
                    "details": {"field": "Idempotency-Key"},
                }
            },
        )
    return idempotency_key.strip()
