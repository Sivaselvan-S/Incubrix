"""API routes for fetching and retrieving publication engagement metrics."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.metrics.service import fetch_and_record_metrics, get_latest_metrics_for_publication

router = APIRouter(prefix="/api/v1/publications", tags=["metrics"])


@router.post("/{publication_id}/metrics", status_code=status.HTTP_201_CREATED)
def trigger_fetch_metrics(publication_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fetches normalized metrics from the external destination platform and stores a snapshot."""
    try:
        return fetch_and_record_metrics(db, publication_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to query destination metrics: {exc}",
        ) from exc


@router.get("/{publication_id}/metrics")
def get_publication_metrics(publication_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Retrieves the latest recorded engagement metrics snapshot for a publication."""
    res = get_latest_metrics_for_publication(db, publication_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metrics recorded for publication '{publication_id}'.",
        )
    return res
