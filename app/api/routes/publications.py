"""Publications API route implementing intent-first idempotency."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_idempotency_key
from app.db.models import DestinationModel, JobModel
from app.idempotency.ledger import check_or_reserve_intent
from app.queue.dispatcher import enqueue_job

router = APIRouter(prefix="/api/v1/publications", tags=["Publications"])


class PublicationRequest(BaseModel):
    """Payload for submitting a content publication."""

    destination_id: str
    content_id: str = "content_001"
    rendition: dict[str, Any] = Field(default_factory=dict)
    callback_url: str | None = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def submit_publication(
    payload: PublicationRequest,
    idempotency_key: str = Depends(require_idempotency_key),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submits a publication request asynchronously.

    Enforces intent-first idempotency before initiating any background job.
    """
    # 1. Validate destination exists
    dest = db.query(DestinationModel).filter(DestinationModel.id == payload.destination_id).first()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DESTINATION_NOT_FOUND",
                    "message": f"Destination '{payload.destination_id}' was not found.",
                    "retryable": False,
                    "details": {"destination_id": payload.destination_id},
                }
            },
        )

    # 2. Check Idempotency Ledger
    req_dict = payload.model_dump()
    action, cached_result = check_or_reserve_intent(db, idempotency_key, req_dict)

    if action == "CACHED":
        # Request with same key and same hash was already processed successfully
        return {
            "status": "cached",
            "idempotency_key": idempotency_key,
            "result": cached_result,
        }

    # 3. Check if a job is already queued/running for this idempotency key
    existing_job = db.query(JobModel).filter(JobModel.idempotency_key == idempotency_key).first()
    if existing_job:
        return {
            "job_id": existing_job.id,
            "status": existing_job.status,
            "idempotency_key": idempotency_key,
        }

    # 4. Enqueue new publication job
    job_payload = {
        "destination_id": payload.destination_id,
        "content_id": payload.content_id,
        "rendition": payload.rendition,
        "idempotency_key": idempotency_key,
    }
    job = enqueue_job(
        db,
        job_type="publication",
        payload=job_payload,
        callback_url=payload.callback_url,
        idempotency_key=idempotency_key,
    )
    db.commit()

    return {
        "job_id": job.id,
        "status": "queued",
        "idempotency_key": idempotency_key,
    }
