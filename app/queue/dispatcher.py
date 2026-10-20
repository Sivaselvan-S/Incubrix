"""Job dispatching, output manifest generation, and HMAC callback delivery."""

import hashlib
import hmac
import json
import time
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import JobModel, generate_uuid, utcnow
from app.logging import get_logger

logger = get_logger("app.queue.dispatcher")


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    callback_url: str | None = None,
) -> JobModel:
    """Inserts a new job in queued state."""
    job = JobModel(
        id=generate_uuid(),
        type=job_type,
        status="queued",
        progress=0,
        payload_json=payload,
        callback_url=callback_url,
        created_at=utcnow(),
    )
    db.add(job)
    db.flush()
    return job


def sign_hmac_sha256(secret: str, timestamp: str, body: str) -> str:
    """Computes HMAC-SHA256 signature: HMAC-SHA256(secret, timestamp.body)."""
    message = f"{timestamp}.{body}".encode()
    signature = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def send_callback(
    callback_url: str,
    result_payload: dict[str, Any],
    secret: str = "incubrix_webhook_secret",
) -> bool:
    """Sends signed webhook notification to callback_url."""
    timestamp = str(int(time.time()))
    body_str = json.dumps(result_payload, sort_keys=True)
    signature = sign_hmac_sha256(secret, timestamp, body_str)

    headers = {
        "Content-Type": "application/json",
        "X-IncuBrix-Signature": signature,
    }

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(callback_url, content=body_str, headers=headers)
            return resp.status_code < 300
    except Exception as exc:
        logger.warning("Callback delivery failed to %s: %s", callback_url, exc)
        return False


def build_output_manifest(
    connector_version: str = "1.0.0",
    passport_fingerprint: str | None = None,
    ai_generated: bool = False,
    timings: dict[str, float] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Generates the standardized result manifest JSON required by Integration Standard #9."""
    settings = get_settings()
    return {
        "providers": [
            {
                "name": settings.LLM_PROVIDER,
                "version": "1.0.0",
                "tier": "mock" if settings.SIMULATION_MODE else "production",
            }
        ],
        "settings": {
            "simulation_mode": settings.SIMULATION_MODE,
            "environment": settings.ENVIRONMENT,
        },
        "seed": 42,
        "timings": timings or {"total_duration_ms": 12.5},
        "cost_estimate": 0.0 if settings.SIMULATION_MODE else 0.002,
        "warnings": warnings or [],
        "rights_license": "Commercial (IncuBrix)",
        "ai_generated": ai_generated,
        "connector_version": connector_version,
        "passport_fingerprint_used": passport_fingerprint or "sha256_uncalibrated",
    }
