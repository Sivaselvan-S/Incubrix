"""Destinations and Passport management API routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DestinationModel, PassportModel, generate_uuid
from app.queue.dispatcher import enqueue_job

router = APIRouter(prefix="/api/v1/destinations", tags=["Destinations & Passports"])


class CreateDestinationRequest(BaseModel):
    """Payload for registering a new publishing destination."""

    name: str
    url: str
    platform_key: str
    surface: str = "community"
    category: str = "general"
    audience_tags: list[str] = Field(default_factory=list)
    language: str = "en"
    geo: str | None = None
    est_audience: int | None = None
    rules_url: str | None = None
    frequency_cap: dict[str, int] = Field(default_factory=lambda: {"max": 1, "per_days": 7})
    self_promo_allowed: bool = True
    link_policy: str = "none"
    disclosure_required: bool = False
    automation_allowed: bool = True
    connector_key: str
    instance_config: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = 0.0
    relevance_reason: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_destination(
    payload: CreateDestinationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Registers a new destination record with default uncertified L0 Passport."""
    dest_id = generate_uuid()
    destination = DestinationModel(
        id=dest_id,
        name=payload.name,
        url=payload.url,
        platform_key=payload.platform_key,
        surface=payload.surface,
        category=payload.category,
        audience_tags=payload.audience_tags,
        language=payload.language,
        geo=payload.geo,
        est_audience=payload.est_audience,
        rules_url=payload.rules_url,
        frequency_cap_json=payload.frequency_cap,
        self_promo_allowed=payload.self_promo_allowed,
        link_policy=payload.link_policy,
        disclosure_required=payload.disclosure_required,
        automation_allowed=payload.automation_allowed,
        connector_key=payload.connector_key,
        instance_config_json=payload.instance_config,
        relevance_score=payload.relevance_score,
        relevance_reason=payload.relevance_reason,
        level="L0",
        status="active",
    )
    db.add(destination)

    # Initialize associated living Passport
    passport = PassportModel(
        destination_id=dest_id,
        level="L0",
        health_score=100.0,
        last_certified_at=None,
        expires_at=None,
    )
    db.add(passport)
    db.commit()
    db.refresh(destination)

    return {
        "id": destination.id,
        "name": destination.name,
        "platform_key": destination.platform_key,
        "connector_key": destination.connector_key,
        "level": destination.level,
        "status": destination.status,
        "record": destination.to_export_dict(),
    }


@router.get("")
def list_destinations(
    platform_key: str | None = Query(None),
    surface: str | None = Query(None),
    level: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Lists destination records with optional filtering."""
    query = db.query(DestinationModel)
    if platform_key:
        query = query.filter(DestinationModel.platform_key == platform_key)
    if surface:
        query = query.filter(DestinationModel.surface == surface)
    if level:
        query = query.filter(DestinationModel.level == level)
    if status_filter:
        query = query.filter(DestinationModel.status == status_filter)

    results = []
    for d in query.all():
        data = d.to_export_dict()
        data["id"] = d.id
        data["status"] = d.status
        results.append(data)
    return results


@router.get("/{destination_id}/passport")
def get_destination_passport(
    destination_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieves the verifiable living Passport for a specific destination."""
    dest = db.query(DestinationModel).filter(DestinationModel.id == destination_id).first()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DESTINATION_NOT_FOUND",
                    "message": f"Destination '{destination_id}' was not found.",
                    "retryable": False,
                    "details": {"destination_id": destination_id},
                }
            },
        )

    passport = dest.passport
    if not passport:
        # Fallback if uninitialized
        passport = PassportModel(destination_id=dest.id, level=dest.level, health_score=100.0)
        db.add(passport)
        db.commit()

    return {
        "destination_id": dest.id,
        "destination_name": dest.name,
        "platform_key": dest.platform_key,
        "level": passport.level,
        "health_score": passport.health_score,
        "schema_fingerprint": passport.schema_fingerprint,
        "last_certified_at": passport.last_certified_at.isoformat()
        if passport.last_certified_at
        else None,
        "expires_at": passport.expires_at.isoformat() if passport.expires_at else None,
        "evidence_uri": passport.evidence_uri,
        "demotion_reason": passport.demotion_reason,
    }


@router.post("/{destination_id}/certify", status_code=status.HTTP_202_ACCEPTED)
def trigger_destination_certification(
    destination_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Queues a certification harness run for a destination."""
    dest = db.query(DestinationModel).filter(DestinationModel.id == destination_id).first()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DESTINATION_NOT_FOUND",
                    "message": f"Destination '{destination_id}' was not found.",
                    "retryable": False,
                    "details": {"destination_id": destination_id},
                }
            },
        )

    job = enqueue_job(
        db,
        job_type="certify",
        payload={"destination_id": dest.id},
    )
    db.commit()

    return {
        "job_id": job.id,
        "destination_id": dest.id,
        "status": "queued",
    }


@router.post("/recertify-stale", status_code=status.HTTP_200_OK)
def trigger_recertify_stale(
    demo_mode: bool = False,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Scans and enqueues recertification jobs for stale passports."""
    from app.passport.scheduler import scan_and_enqueue_recertifications

    result = scan_and_enqueue_recertifications(db, demo_mode=demo_mode)
    db.commit()
    return result

