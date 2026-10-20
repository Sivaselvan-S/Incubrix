"""Generic connector runtime router: POST /connector/v1/{connector_key}/{method}."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.connectors.registry import get_connector
from app.db.models import ConnectorModel

router = APIRouter(prefix="/connector/v1", tags=["Connector Runtime"])


class ConnectorRuntimeRequest(BaseModel):
    """Payload for executing a method on a connector."""

    rendition: dict[str, Any] = Field(default_factory=dict)
    destination: dict[str, Any] = Field(default_factory=dict)
    connection: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    platform_post_id: str | None = None
    since: str | None = None


@router.post("/{connector_key}/{method}")
def execute_connector_method(
    connector_key: str,
    method: str,
    payload: ConnectorRuntimeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Dynamically executes a method against a connector instance looked up by key.

    Does not contain any hardcoded platform if/else branches.
    """
    # 1. Lookup connector in dynamic registry
    try:
        connector = get_connector(connector_key)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CONNECTOR_NOT_FOUND",
                    "message": f"Connector with key '{connector_key}' is not registered.",
                    "retryable": False,
                    "details": {"connector_key": connector_key},
                }
            },
        ) from None

    # 2. Check DB status (kill switch & circuit breaker) if record exists
    db_connector = db.query(ConnectorModel).filter(ConnectorModel.key == connector_key).first()
    if db_connector:
        if not db_connector.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "CONNECTOR_DISABLED",
                        "message": f"Connector '{connector_key}' is disabled by kill switch.",
                        "retryable": False,
                        "details": {"connector_key": connector_key},
                    }
                },
            )
        if db_connector.consecutive_failures >= 5:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": {
                        "code": "PLATFORM_UNAVAILABLE",
                        "message": f"Connector '{connector_key}' circuit breaker is open (consecutive failures: {db_connector.consecutive_failures}).",
                        "retryable": True,
                        "details": {"connector_key": connector_key},
                    }
                },
            )

    # 3. Dispatch to contract method
    if method == "validate":
        return connector.validate(
            rendition=payload.rendition,
            destination=payload.destination,
            connection=payload.connection,
        )
    elif method == "publish":
        if not payload.idempotency_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Field 'idempotency_key' is required when calling 'publish'.",
                        "retryable": False,
                        "details": {"field": "idempotency_key"},
                    }
                },
            )
        return connector.publish(
            rendition=payload.rendition,
            destination=payload.destination,
            connection=payload.connection,
            idempotency_key=payload.idempotency_key,
        )
    elif method == "get_status":
        if not payload.platform_post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Field 'platform_post_id' is required when calling 'get_status'.",
                        "retryable": False,
                        "details": {"field": "platform_post_id"},
                    }
                },
            )
        return connector.get_status(
            platform_post_id=payload.platform_post_id,
            connection=payload.connection,
        )
    elif method == "delete":
        if not payload.platform_post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Field 'platform_post_id' is required when calling 'delete'.",
                        "retryable": False,
                        "details": {"field": "platform_post_id"},
                    }
                },
            )
        return connector.delete(
            platform_post_id=payload.platform_post_id,
            connection=payload.connection,
        )
    elif method == "fetch_metrics":
        if not payload.platform_post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Field 'platform_post_id' is required when calling 'fetch_metrics'.",
                        "retryable": False,
                        "details": {"field": "platform_post_id"},
                    }
                },
            )
        return connector.fetch_metrics(
            platform_post_id=payload.platform_post_id,
            connection=payload.connection,
        )
    elif method == "refresh_auth":
        return connector.refresh_auth(connection=payload.connection)
    elif method == "build_assist_pack":
        return connector.build_assist_pack(
            rendition=payload.rendition,
            destination=payload.destination,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Method '{method}' is not supported by connector contract.",
                    "retryable": False,
                    "details": {"method": method},
                }
            },
        )
