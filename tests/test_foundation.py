"""Foundation tests: health, readiness, correlation ID, DB models, and secret redaction."""

import io
import logging
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    AlertModel,
    CertificationModel,
    ConnectionModel,
    ConnectorModel,
    DestinationModel,
    IdempotencyLedgerModel,
    JobModel,
    MetricsModel,
    PassportModel,
    PostHistoryModel,
    PublicationModel,
    utcnow,
)
from app.logging import JSONFormatter, SecretRedactionFilter


def test_health_check(client: TestClient):
    """Assert /health returns 200 with service metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "LongTail Passport"
    assert data["simulation_mode"] is True


def test_readiness_check(client: TestClient):
    """Assert /ready checks database and storage successfully."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert "ok" in data["checks"]["storage"]


def test_correlation_id_middleware(client: TestClient):
    """Assert X-Correlation-Id header is echoed or generated if absent."""
    custom_id = "test-corr-" + str(uuid.uuid4())
    res = client.get("/health", headers={"X-Correlation-Id": custom_id})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-Id") == custom_id

    # Absent header generates a fresh UUID
    res2 = client.get("/health")
    assert res2.status_code == 200
    assert res2.headers.get("X-Correlation-Id") is not None


def test_secret_redaction_in_logging():
    """Assert SecretRedactionFilter scrubs token, secret, password, and api_key."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SecretRedactionFilter())

    test_logger = logging.getLogger("test_redact")
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    test_logger.info("Connecting with password: my_super_secret_password_123")
    test_logger.info("Header authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6")
    test_logger.info("Setting api_key=abc123secrettokenxyz")

    output = log_stream.getvalue()
    assert "my_super_secret_password_123" not in output
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6" not in output
    assert "abc123secrettokenxyz" not in output
    assert "[REDACTED]" in output


def test_all_11_models_crud(db_session: Session):
    """Assert all 11 database models can be instantiated and persisted cleanly."""
    # 1. Connector
    connector = ConnectorModel(key="test_connector", version="1.0.0", enabled=True)
    db_session.add(connector)
    db_session.flush()

    # 2. Destination
    dest = DestinationModel(
        id=str(uuid.uuid4()),
        name="Test Discourse Forum",
        url="https://forum.example.com",
        platform_key="discourse",
        surface="forum",
        category="tech",
        audience_tags=["AI", "developers"],
        language="en",
        connector_key="test_connector",
        self_promo_allowed=False,
        link_policy="max_n",
        disclosure_required=True,
    )
    db_session.add(dest)
    db_session.flush()

    # Verify export dict contains all 20 required fields
    exported = dest.to_export_dict()
    assert len(exported) == 20
    assert exported["name"] == "Test Discourse Forum"
    assert exported["connector_key"] == "test_connector"

    # 3. Connection
    conn = ConnectionModel(
        connector_key="test_connector",
        destination_id=dest.id,
        secret_ref="DISCOURSE_API_KEY",
    )
    db_session.add(conn)

    # 4. Passport
    passport = PassportModel(
        destination_id=dest.id,
        level="L1",
        health_score=95.0,
        schema_fingerprint="abc_fingerprint_123",
        last_certified_at=utcnow(),
    )
    db_session.add(passport)

    # 5. Publication
    pub = PublicationModel(
        destination_id=dest.id,
        content_id="post_001",
        idempotency_key="key_001",
        state="INTENT",
    )
    db_session.add(pub)

    # 6. Idempotency Ledger
    ledger = IdempotencyLedgerModel(
        key="key_001",
        request_hash="hash_001",
        state="INTENT",
    )
    db_session.add(ledger)

    # 7. Job
    job = JobModel(
        id=str(uuid.uuid4()),
        type="publication",
        status="queued",
        progress=0,
        payload_json={"content_id": "post_001"},
    )
    db_session.add(job)

    # 8. Certification
    cert = CertificationModel(
        destination_id=dest.id,
        passed=True,
        steps_json=[{"step": "validate", "passed": True}],
    )
    db_session.add(cert)

    # 9. Alert
    alert = AlertModel(
        kind="CERT_DRIFT_DETECTED",
        destination_id=dest.id,
        message="Schema drifted on live_url",
    )
    db_session.add(alert)

    # 10. Post History
    history = PostHistoryModel(
        destination_id=dest.id,
        posted_at=utcnow(),
        promotional=True,
    )
    db_session.add(history)

    # 11. Metrics
    metric = MetricsModel(
        platform_post_id="ext_post_123",
        views=150,
        likes=25,
        comments=5,
    )
    db_session.add(metric)
    db_session.commit()

    # Query back to verify persistence
    queried_dest = db_session.query(DestinationModel).filter_by(name="Test Discourse Forum").first()
    assert queried_dest is not None
    assert queried_dest.passport.level == "L1"
    assert queried_dest.passport.health_score == 95.0
