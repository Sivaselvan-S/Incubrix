"""API routes for extracting and confirming destination rules."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import AuditLogModel, DestinationModel
from app.rules_capture.extractor import extract_rules_from_text

router = APIRouter(prefix="/api/v1/rules", tags=["rules-capture"])


class ExtractRulesRequest(BaseModel):
    """Payload containing raw policy or community guidelines text."""

    text: str = Field(..., description="Community guidelines or terms of service text.")
    url: str | None = Field(None, description="Optional source policy URL.")


class ConfirmRulesRequest(BaseModel):
    """Payload to record human verification and apply confirmed rules to a destination."""

    destination_id: str
    confirmed_rules: dict[str, Any]
    actor: str = Field("editorial_staff", description="Username or ID of the human reviewer.")


@router.post("/extract")
def extract_rules(payload: ExtractRulesRequest) -> dict[str, Any]:
    """Parses unformatted policy text and returns proposed rule constraints with confidence."""
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Policy text cannot be empty.",
        )
    return extract_rules_from_text(payload.text)


@router.post("/confirm")
def confirm_rules(payload: ConfirmRulesRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Records human confirmation of destination rules and writes an immutable audit log entry."""
    dest = db.query(DestinationModel).filter(DestinationModel.id == payload.destination_id).first()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination '{payload.destination_id}' not found.",
        )

    old_rules = {
        "frequency_cap": dest.frequency_cap_json,
        "self_promo_allowed": dest.self_promo_allowed,
        "link_policy": dest.link_policy,
        "disclosure_required": dest.disclosure_required,
        "automation_allowed": dest.automation_allowed,
    }

    rules = payload.confirmed_rules
    if "frequency_cap" in rules:
        dest.frequency_cap_json = rules["frequency_cap"]
    if "self_promo_allowed" in rules:
        dest.self_promo_allowed = bool(rules["self_promo_allowed"])
    if "link_policy" in rules:
        dest.link_policy = str(rules["link_policy"])
    if "disclosure_required" in rules:
        dest.disclosure_required = bool(rules["disclosure_required"])
    if "automation_allowed" in rules:
        dest.automation_allowed = bool(rules["automation_allowed"])

    now = datetime.now(UTC)
    dest.rules_confirmed_by = payload.actor
    dest.rules_confirmed_at = now

    diff = {
        "before": old_rules,
        "after": {
            "frequency_cap": dest.frequency_cap_json,
            "self_promo_allowed": dest.self_promo_allowed,
            "link_policy": dest.link_policy,
            "disclosure_required": dest.disclosure_required,
            "automation_allowed": dest.automation_allowed,
        },
    }

    # Record in audit log
    audit_log = AuditLogModel(
        entity_type="destination",
        entity_id=dest.id,
        action="RULES_CONFIRMED",
        actor=payload.actor,
        diff_json=diff,
        created_at=now,
    )
    db.add(audit_log)
    db.commit()

    return {
        "status": "confirmed",
        "destination_id": dest.id,
        "rules_confirmed_by": dest.rules_confirmed_by,
        "rules_confirmed_at": dest.rules_confirmed_at.isoformat(),
        "applied_rules": diff["after"],
    }
