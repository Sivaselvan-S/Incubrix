"""Intent-first idempotency ledger manager preventing duplicate publications."""

import hashlib
import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import IdempotencyLedgerModel, utcnow


def compute_request_hash(payload: Any) -> str:
    """Computes a deterministic SHA-256 hash of a normalized JSON payload."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def embed_marker(text: str, idempotency_key: str) -> str:
    """Embeds an invisible HTML comment marker to enable post-timeout reconciliation."""
    marker = f"<!-- ibx:{idempotency_key} -->"
    if marker in text:
        return text
    return f"{text}\n\n{marker}"


def check_or_reserve_intent(
    db: Session,
    key: str,
    payload: Any,
) -> tuple[str, dict[str, Any] | None]:
    """Inspects the idempotency ledger.

    Returns:
        tuple (action, existing_result)
        where action is "NEW", "CACHED", or "RECONCILE".
    Raises:
        HTTPException 409 IDEMPOTENCY_KEY_REUSED if key exists with different payload hash.
    """
    req_hash = compute_request_hash(payload)
    existing: IdempotencyLedgerModel | None = (
        db.query(IdempotencyLedgerModel).filter(IdempotencyLedgerModel.key == key).first()
    )

    if not existing:
        # First time seeing this key: reserve intent immediately in DB
        ledger_entry = IdempotencyLedgerModel(
            key=key,
            request_hash=req_hash,
            state="INTENT",
            updated_at=utcnow(),
        )
        db.add(ledger_entry)
        db.flush()
        return "NEW", None

    # Key was seen before: verify payload hash matches
    if existing.request_hash != req_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "IDEMPOTENCY_KEY_REUSED",
                    "message": f"Idempotency key '{key}' was previously used with a different request payload.",
                    "retryable": False,
                    "details": {
                        "idempotency_key": key,
                        "stored_hash": existing.request_hash,
                        "current_hash": req_hash,
                    },
                }
            },
        )

    # Payload matches: if succeeded, return cached result
    if existing.state == "SUCCEEDED" and existing.result_json:
        return "CACHED", existing.result_json

    # If state is UNKNOWN or INTENT, caller should reconcile with platform
    return "RECONCILE", existing.result_json


def record_success(db: Session, key: str, result_json: dict[str, Any]) -> None:
    """Marks ledger row as SUCCEEDED and caches the response JSON."""
    entry: IdempotencyLedgerModel | None = (
        db.query(IdempotencyLedgerModel).filter(IdempotencyLedgerModel.key == key).first()
    )
    if entry:
        entry.state = "SUCCEEDED"
        entry.result_json = result_json
        entry.updated_at = utcnow()
        db.flush()


def record_unknown(db: Session, key: str) -> None:
    """Marks ledger row as UNKNOWN (e.g. platform call timed out)."""
    entry: IdempotencyLedgerModel | None = (
        db.query(IdempotencyLedgerModel).filter(IdempotencyLedgerModel.key == key).first()
    )
    if entry:
        entry.state = "UNKNOWN"
        entry.updated_at = utcnow()
        db.flush()


def record_failure(db: Session, key: str, error_json: dict[str, Any]) -> None:
    """Marks ledger row as FAILED."""
    entry: IdempotencyLedgerModel | None = (
        db.query(IdempotencyLedgerModel).filter(IdempotencyLedgerModel.key == key).first()
    )
    if entry:
        entry.state = "FAILED"
        entry.result_json = {"error": error_json}
        entry.updated_at = utcnow()
        db.flush()
