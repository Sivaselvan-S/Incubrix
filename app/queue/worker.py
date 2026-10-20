"""Background worker claiming jobs via SELECT ... FOR UPDATE SKIP LOCKED."""

import time
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.registry import get_connector
from app.db.models import (
    DestinationModel,
    JobModel,
    PublicationModel,
)
from app.db.session import SessionLocal, engine
from app.idempotency.ledger import (
    embed_marker,
    record_failure,
    record_success,
    record_unknown,
)
from app.logging import get_logger, job_id_ctx
from app.queue.dispatcher import build_output_manifest, send_callback
from app.rules.court import evaluate
from app.rules.schemas import (
    DestinationRuleContext,
    Rendition,
    SurfaceSpec,
    VerdictEnum,
)

logger = get_logger("app.queue.worker")


def claim_next_job(db: Session) -> JobModel | None:
    """Claims the oldest queued job atomically using SELECT FOR UPDATE SKIP LOCKED."""
    is_postgres = "postgres" in engine.url.drivername.lower()

    query = (
        db.query(JobModel).filter(JobModel.status == "queued").order_by(JobModel.created_at.asc())
    )

    if is_postgres:
        # Atomic lock skipping already-claimed rows
        job = query.with_for_update(skip_locked=True).first()
    else:
        # SQLite transactional fallback
        job = query.first()

    if job:
        job.status = "running"
        job.progress = 10
        db.commit()
        db.refresh(job)
        return job
    return None


def execute_publication_job(db: Session, job: JobModel) -> dict[str, Any]:
    """Executes an asynchronous publication workflow.

    Tailor -> Preflight Court -> connector.publish -> Result & Output Manifest.
    """
    payload = job.payload_json
    destination_id = payload.get("destination_id")
    raw_rendition = payload.get("rendition", {})
    idempotency_key = payload.get("idempotency_key", "")
    content_id = payload.get("content_id", "content_default")

    # 1. Load destination and passport
    dest = db.query(DestinationModel).filter(DestinationModel.id == destination_id).first()
    if not dest:
        raise ValueError(f"Destination '{destination_id}' not found.")

    passport = dest.passport
    fingerprint = passport.schema_fingerprint if passport else None
    connector_key = dest.connector_key

    job.progress = 25
    db.commit()

    # 2. Run Preflight Court
    rendition = Rendition(**raw_rendition)
    rule_ctx = DestinationRuleContext(
        connector_enabled=dest.connector.enabled if dest.connector else True,
        circuit_open=bool(dest.connector and dest.connector.consecutive_failures >= 5),
        destination_status=dest.status,
        automation_allowed=dest.automation_allowed,
        self_promo_allowed=dest.self_promo_allowed,
        link_policy=dest.link_policy,
        disclosure_required=dest.disclosure_required,
        frequency_cap=dest.frequency_cap_json or {"max": 1, "per_days": 7},
        language=dest.language,
    )

    verdict = evaluate(rendition, rule_ctx, history=[], surface_spec=SurfaceSpec())

    if verdict.verdict == VerdictEnum.BLOCK:
        err_data = {
            "code": verdict.code or "PREFLIGHT_BLOCKED",
            "message": verdict.reason,
            "rule_id": verdict.rule_id,
            "violations": [v.model_dump() for v in verdict.violations],
        }
        record_failure(db, idempotency_key, err_data)
        raise ValueError(f"Preflight Court BLOCKED post: {verdict.reason}")

    # Use rewritten rendition if Court auto-adjusted format
    active_rendition = verdict.rewritten_rendition if verdict.rewritten_rendition else rendition

    job.progress = 50
    db.commit()

    # 3. Handle Assisted vs Native Publishing
    connector = get_connector(connector_key)
    if verdict.verdict == VerdictEnum.ASSIST or not dest.automation_allowed:
        pack = connector.build_assist_pack(active_rendition.model_dump(), dest.to_export_dict())
        manifest = build_output_manifest(
            connector_version=dest.connector.version if dest.connector else "1.0.0",
            passport_fingerprint=fingerprint,
            ai_generated=active_rendition.ai_generated,
            warnings=verdict.warnings,
        )
        result = {
            "status": "assisted_pack_ready",
            "pack": pack,
            "manifest": manifest,
        }
        record_success(db, idempotency_key, result)
        job.progress = 100
        return result

    # 4. Native publish: Embed reconciliation marker
    rendition_dict = active_rendition.model_dump()
    rendition_dict["body"] = embed_marker(rendition_dict.get("body", ""), idempotency_key)

    job.progress = 75
    db.commit()

    try:
        publish_result = connector.publish(
            rendition=rendition_dict,
            destination=dest.to_export_dict(),
            connection={"destination_id": dest.id},
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        record_unknown(db, idempotency_key)
        raise exc

    # 5. Build Final Output Manifest and Record Publication
    manifest = build_output_manifest(
        connector_version=dest.connector.version if dest.connector else "1.0.0",
        passport_fingerprint=fingerprint,
        ai_generated=active_rendition.ai_generated,
        warnings=verdict.warnings,
    )

    result_data = {
        "platform_post_id": publish_result.get("platform_post_id"),
        "live_url": publish_result.get("live_url"),
        "status": publish_result.get("status", "published"),
        "manifest": manifest,
    }

    # Record in publications table
    pub_record = PublicationModel(
        destination_id=dest.id,
        content_id=content_id,
        idempotency_key=idempotency_key,
        state="SUCCEEDED",
        platform_post_id=result_data["platform_post_id"],
        live_url=result_data["live_url"],
        attempts=1,
    )
    db.add(pub_record)

    # Record in idempotency ledger
    record_success(db, idempotency_key, result_data)

    job.progress = 100
    return result_data


def process_single_job(job_id: str, db: Session | None = None) -> None:
    """Processes a single claimed job in a session."""
    if db is not None:
        _process_single_job_internal(db, job_id)
        return

    with SessionLocal() as session:
        _process_single_job_internal(session, job_id)


def _process_single_job_internal(db: Session, job_id: str) -> None:
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        return

    token = job_id_ctx.set(job.id)
    try:
        logger.info("Executing job %s (type: %s)...", job.id, job.type)
        if job.type == "publication":
            result = execute_publication_job(db, job)
            job.status = "succeeded"
            job.result_json = result
            job.progress = 100
        else:
            job.status = "succeeded"
            job.progress = 100
            job.result_json = {"message": f"Job type '{job.type}' executed successfully."}

        db.commit()

        # Deliver webhook callback if requested
        if job.callback_url:
            send_callback(job.callback_url, job.result_json or {})

        logger.info("Job %s completed successfully.", job.id)
    except Exception as exc:
        logger.exception("Job %s failed: %s", job.id, exc)
        job.status = "failed"
        job.error_json = {
            "error": {
                "code": "JOB_FAILED",
                "message": str(exc),
                "retryable": False,
            }
        }
        db.commit()
    finally:
        job_id_ctx.reset(token)


def run_worker_loop(single_run: bool = False, max_jobs: int | None = None) -> None:
    """Continuously runs the background job claim loop."""
    settings = get_settings()
    processed_count = 0

    logger.info("Background job worker loop started.")
    while True:
        with SessionLocal() as db:
            job = claim_next_job(db)

        if job:
            process_single_job(job.id)
            processed_count += 1
            if max_jobs and processed_count >= max_jobs:
                break
        else:
            if single_run:
                break
            time.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker_loop()
