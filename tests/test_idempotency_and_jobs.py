"""Tests for intent-first idempotency ledger, background job queue, and worker execution."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.connectors.base import BaseConnector, ConnectorManifest
from app.connectors.registry import register_connector
from app.db.models import ConnectorModel, DestinationModel, JobModel
from app.idempotency.ledger import (
    embed_marker,
)
from app.queue.dispatcher import build_output_manifest, sign_hmac_sha256
from app.queue.worker import process_single_job


class MockWorkerConnector(BaseConnector):
    """Mock connector for verifying worker publication flow."""

    def __init__(self):
        self.manifest = ConnectorManifest(
            key="worker_mock_conn",
            version="1.0.0",
            tier="native",
        )
        self.published_posts = []

    def validate(self, rendition, destination, connection):
        return {"ok": True, "violations": []}

    def publish(self, rendition, destination, connection, idempotency_key):
        self.published_posts.append({"rendition": rendition, "idempotency_key": idempotency_key})
        return {
            "platform_post_id": f"pub_{idempotency_key}",
            "live_url": f"https://mock.platform/post/{idempotency_key}",
            "status": "published",
        }

    def get_status(self, platform_post_id, connection):
        return {"status": "published", "live_url": f"https://mock.platform/post/{platform_post_id}"}

    def delete(self, platform_post_id, connection):
        return {"deleted": True}


@pytest.fixture
def worker_connector():
    conn = MockWorkerConnector()
    register_connector("worker_mock_conn", conn)
    return conn


@pytest.fixture
def destination_fixture(db_session: Session, worker_connector):
    """Sets up a registered connector and active destination."""
    connector = ConnectorModel(key="worker_mock_conn", version="1.0.0", enabled=True)
    db_session.add(connector)
    dest = DestinationModel(
        id="dest_worker_001",
        name="Worker Test Destination",
        url="https://forum.example.com",
        platform_key="worker_mock_conn",
        connector_key="worker_mock_conn",
        status="active",
        automation_allowed=True,
    )
    db_session.add(dest)
    db_session.commit()
    return dest


def test_idempotency_key_header_required(client: TestClient, destination_fixture):
    """Asserts POST /api/v1/publications rejects requests without Idempotency-Key."""
    res = client.post(
        "/api/v1/publications",
        json={
            "destination_id": destination_fixture.id,
            "rendition": {"title": "Test Title", "body": "Content body"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "Idempotency-Key" in res.json()["error"]["message"]


def test_intent_first_idempotency_lifecycle(
    client: TestClient, destination_fixture, db_session: Session
):
    """Asserts intent is reserved first, same key + same hash returns result, diff hash returns 409."""
    key = "idem_test_key_001"
    payload = {
        "destination_id": destination_fixture.id,
        "content_id": "item_123",
        "rendition": {"title": "Post 1", "body": "Hello World"},
    }

    # 1. First submission reserves intent and enqueues job
    res1 = client.post(
        "/api/v1/publications",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert res1.status_code == 202
    job_id = res1.json()["job_id"]
    assert job_id is not None
    assert res1.json()["status"] == "queued"

    # 2. Worker executes job to completion
    process_single_job(job_id, db=db_session)

    # Verify job status in DB
    job_after = db_session.query(JobModel).filter(JobModel.id == job_id).first()
    assert job_after.status == "succeeded"
    assert job_after.progress == 100

    # 3. Re-submitting with identical key and payload returns cached result
    res_cached = client.post(
        "/api/v1/publications",
        json=payload,
        headers={"Idempotency-Key": key},
    )
    assert res_cached.status_code == 202 or res_cached.status_code == 200
    data_cached = res_cached.json()
    assert data_cached.get("status") == "cached" or data_cached.get("status") == "succeeded"

    # 4. Re-submitting with same key but DIFFERENT payload returns 409 IDEMPOTENCY_KEY_REUSED
    altered_payload = {
        "destination_id": destination_fixture.id,
        "content_id": "item_123",
        "rendition": {"title": "DIFFERENT Title", "body": "Different body"},
    }
    res_reused = client.post(
        "/api/v1/publications",
        json=altered_payload,
        headers={"Idempotency-Key": key},
    )
    assert res_reused.status_code == 409
    assert res_reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_get_job_status_and_not_found(client: TestClient, destination_fixture, db_session: Session):
    """Asserts GET /api/v1/jobs/{job_id} reports status and links, or 404 if missing."""
    # 1. 404 on non-existent job
    res_404 = client.get("/api/v1/jobs/non_existent_job_id")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "JOB_NOT_FOUND"

    # 2. Enqueue and check queued status
    res = client.post(
        "/api/v1/publications",
        json={
            "destination_id": destination_fixture.id,
            "rendition": {"title": "Test Title", "body": "Body"},
        },
        headers={"Idempotency-Key": "job_status_test_key"},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    res_poll = client.get(f"/api/v1/jobs/{job_id}")
    assert res_poll.status_code == 200
    assert res_poll.json()["status"] == "queued"

    # Process job and verify final report
    process_single_job(job_id, db=db_session)
    res_completed = client.get(f"/api/v1/jobs/{job_id}")
    assert res_completed.status_code == 200
    data = res_completed.json()
    assert data["status"] == "succeeded"
    assert data["progress"] == 100
    assert len(data["result_links"]) >= 1
    assert "https://mock.platform/post/" in data["result_links"][0]


def test_embed_reconciliation_marker():
    """Asserts invisible HTML reconciliation marker is cleanly embedded."""
    body = "A comprehensive guide on Kubernetes operators."
    key = "ibx_key_abc789"
    marked = embed_marker(body, key)
    assert f"<!-- ibx:{key} -->" in marked
    assert marked.startswith(body)

    # Calling again does not duplicate marker
    marked_again = embed_marker(marked, key)
    assert marked_again.count(f"<!-- ibx:{key} -->") == 1


def test_hmac_sha256_webhook_signature():
    """Asserts HMAC-SHA256 signature matches expected format and verification."""
    secret = "my_secret_signing_key"
    timestamp = "1729425000"
    body = '{"event":"post_completed"}'
    sig = sign_hmac_sha256(secret, timestamp, body)
    assert sig.startswith("t=1729425000,v1=")

    # Same inputs yield identical signature
    assert sig == sign_hmac_sha256(secret, timestamp, body)
    # Altered body yields different signature
    assert sig != sign_hmac_sha256(secret, timestamp, '{"event":"altered"}')


def test_output_manifest_standard_fields():
    """Asserts build_output_manifest satisfies all Integration Standard #9 keys."""
    manifest = build_output_manifest(
        connector_version="2.1.0",
        passport_fingerprint="fp_hash_xyz",
        ai_generated=True,
    )
    required_keys = [
        "providers",
        "settings",
        "seed",
        "timings",
        "cost_estimate",
        "warnings",
        "rights_license",
        "ai_generated",
        "connector_version",
        "passport_fingerprint_used",
    ]
    for k in required_keys:
        assert k in manifest, f"Missing required manifest key: {k}"
    assert manifest["connector_version"] == "2.1.0"
    assert manifest["passport_fingerprint_used"] == "fp_hash_xyz"
    assert manifest["ai_generated"] is True
