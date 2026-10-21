"""Periodic recertification scheduler discovering stale Passports and enqueuing re-test jobs."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import DestinationModel, PassportModel
from app.logging import get_logger
from app.queue.dispatcher import enqueue_job

logger = get_logger("app.passport.scheduler")


def scan_and_enqueue_recertifications(
    db: Session,
    max_age_days: int = 25,
    demo_mode: bool = False,
) -> dict[str, Any]:
    """Scans Passports requiring recertification and schedules background certify jobs.

    In production: triggers for passports older than 25 days.
    In demo/test mode: triggers for passports older than 10 seconds.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    if demo_mode:
        cutoff = now - timedelta(seconds=settings.DEMO_RECERTIFICATION_INTERVAL_SECONDS)
    else:
        cutoff = now - timedelta(days=max_age_days)

    # Query active destinations whose passports have not been certified recently
    query = (
        db.query(PassportModel)
        .join(DestinationModel)
        .filter(
            DestinationModel.status == "active",
            PassportModel.level != "L0",
            (PassportModel.last_certified_at.is_(None)) | (PassportModel.last_certified_at <= cutoff),
        )
    )
    stale_passports = query.all()

    enqueued_jobs: list[str] = []
    for passport in stale_passports:
        job = enqueue_job(
            db,
            job_type="certify",
            payload={"destination_id": passport.destination_id},
        )
        enqueued_jobs.append(job.id)
        logger.info(
            "Scheduled recertification job %s for destination %s (last certified: %s)",
            job.id,
            passport.destination_id,
            passport.last_certified_at,
        )

    return {
        "stale_count": len(stale_passports),
        "enqueued_job_ids": enqueued_jobs,
        "cutoff_used": cutoff.isoformat(),
    }
