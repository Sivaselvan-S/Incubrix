"""Preflight Court API endpoint."""

from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DestinationModel, PostHistoryModel
from app.rules.court import evaluate
from app.rules.schemas import (
    CourtVerdict,
    DestinationRuleContext,
    PostHistoryItem,
    Rendition,
    SurfaceSpec,
)

router = APIRouter(prefix="/api/v1/preflight", tags=["Preflight Court"])


class PreflightRequest(BaseModel):
    """Payload for dry-run preflight evaluation."""

    destination_id: str
    rendition: Rendition
    surface_spec: SurfaceSpec | None = None


@router.post("", response_model=CourtVerdict)
def evaluate_preflight(
    req: PreflightRequest,
    db: Session = Depends(get_db),
) -> CourtVerdict:
    """Synchronously evaluates a rendition against a destination's rules without publishing."""
    dest = db.query(DestinationModel).filter(DestinationModel.id == req.destination_id).first()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DESTINATION_NOT_FOUND",
                    "message": f"Destination with id '{req.destination_id}' was not found.",
                    "retryable": False,
                    "details": {"destination_id": req.destination_id},
                }
            },
        )

    # Check connector circuit breaker & enabled status
    connector = dest.connector
    conn_enabled = connector.enabled if connector else True
    circuit_open = False
    if connector and connector.consecutive_failures >= 5:
        circuit_open = True

    # Assemble rule context from destination record & passport
    passport = dest.passport
    passport_expired = False
    if passport and passport.expires_at:
        from datetime import UTC, datetime

        exp = passport.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            passport_expired = True

    rule_ctx = DestinationRuleContext(
        connector_enabled=conn_enabled,
        circuit_open=circuit_open,
        destination_status=dest.status,
        passport_expired=passport_expired,
        automation_allowed=dest.automation_allowed,
        self_promo_allowed=dest.self_promo_allowed,
        link_policy=dest.link_policy,
        link_policy_config={},
        disclosure_required=dest.disclosure_required,
        frequency_cap=dest.frequency_cap_json or {"max": 1, "per_days": 7},
        language=dest.language,
    )

    # Fetch recent post history
    db_history = (
        db.query(PostHistoryModel)
        .filter(PostHistoryModel.destination_id == dest.id)
        .order_by(PostHistoryModel.posted_at.desc())
        .limit(50)
        .all()
    )
    history_items = [
        PostHistoryItem(posted_at=h.posted_at, promotional=h.promotional) for h in db_history
    ]

    # Evaluate pure function
    verdict = evaluate(
        rendition=req.rendition,
        destination=rule_ctx,
        history=history_items,
        surface_spec=req.surface_spec or SurfaceSpec(),
    )
    return verdict
