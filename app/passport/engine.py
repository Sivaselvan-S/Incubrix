"""Passport engine: level calculation (L0-L4), health score, expiry, and auto-demotion."""

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    AlertModel,
    DestinationModel,
    PassportModel,
    generate_uuid,
    utcnow,
)
from app.logging import get_logger

logger = get_logger("app.passport.engine")


def calculate_certified_level(
    tier: str,
    capabilities: dict[str, Any],
    drift_checked: bool = True,
) -> str:
    """Calculates Passport certification level according to the L0-L4 specification.

    L0: Uncertified / demoted
    L1: Assisted tier verified
    L2: Native publish + get_status verified
    L3: Native publish + get_status + metrics verified
    L4: Autonomous certified with Drift Canary response pinned
    """
    if tier == "assisted":
        return "L1"

    can_publish = capabilities.get("can_publish", False)
    can_metrics = capabilities.get("can_fetch_metrics", False)

    if not can_publish:
        return "L0"

    if can_publish and can_metrics and drift_checked:
        return "L4"
    elif can_publish and can_metrics:
        return "L3"
    elif can_publish:
        return "L2"
    return "L1"


def update_passport_success(
    db: Session,
    destination_id: str,
    tier: str,
    capabilities: dict[str, Any],
    fingerprint: str,
    evidence_uri: str,
) -> PassportModel:
    """Updates Passport upon successful certification harness run."""
    dest = db.query(DestinationModel).filter(DestinationModel.id == destination_id).first()
    if not dest:
        raise ValueError(f"Destination '{destination_id}' not found.")

    passport = dest.passport
    if not passport:
        passport = PassportModel(destination_id=destination_id)
        db.add(passport)

    now = utcnow()
    level = calculate_certified_level(tier, capabilities, drift_checked=True)

    passport.level = level
    passport.schema_fingerprint = fingerprint
    passport.last_certified_at = now
    passport.expires_at = now + timedelta(days=30)
    passport.health_score = min(100.0, passport.health_score + 10.0)
    passport.evidence_uri = evidence_uri
    passport.demotion_reason = None

    # Sync destination state
    dest.level = level
    dest.last_certified_at = now
    dest.status = "active"

    db.flush()
    logger.info(
        "Passport for destination %s promoted to %s (health: %.1f)",
        dest.name,
        level,
        passport.health_score,
    )
    return passport


def demote_destination(
    db: Session,
    destination_id: str,
    reason: str,
    error_code: str = "CERT_DRIFT_DETECTED",
) -> tuple[DestinationModel, AlertModel]:
    """Auto-demotes a destination and its Passport, writing an Alert record.

    Causes Preflight Court to immediately block publishing to this destination.
    """
    dest = db.query(DestinationModel).filter(DestinationModel.id == destination_id).first()
    if not dest:
        raise ValueError(f"Destination '{destination_id}' not found.")

    passport = dest.passport
    if not passport:
        passport = PassportModel(destination_id=destination_id)
        db.add(passport)

    # Demote level to L0 and degrade health score
    passport.level = "L0"
    passport.health_score = max(0.0, passport.health_score - 50.0)
    passport.demotion_reason = reason

    # Update destination status
    dest.level = "L0"
    dest.status = "demoted"

    # Write alert record
    alert = AlertModel(
        id=generate_uuid(),
        kind=error_code,
        destination_id=dest.id,
        message=reason,
        created_at=utcnow(),
        resolved=False,
    )
    db.add(alert)
    db.flush()

    logger.warning(
        "Destination '%s' AUTO-DEMOTED to L0: %s (Alert: %s)", dest.name, reason, alert.kind
    )
    return dest, alert
