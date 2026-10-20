"""Job status polling API route."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import JobModel

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Queries the current status, progress, and result links of a background job."""
    job = db.query(JobModel).filter(JobModel.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job with id '{job_id}' does not exist.",
                    "retryable": False,
                    "details": {"job_id": job_id},
                }
            },
        )

    # Extract result links if present
    result_links = []
    if job.result_json and isinstance(job.result_json, dict):
        if "live_url" in job.result_json and job.result_json["live_url"]:
            result_links.append(job.result_json["live_url"])
        if "evidence_uri" in job.result_json and job.result_json["evidence_uri"]:
            result_links.append(job.result_json["evidence_uri"])

    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "progress": job.progress,
        "result_links": result_links,
        "result": job.result_json,
        "error": job.error_json,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
