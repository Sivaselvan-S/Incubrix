"""Tests for the 7-step Certification Harness, MinIO evidence bundling, and Passport promotion."""

import httpx
import pytest
from starlette.testclient import TestClient

from app.certify.harness import run_certification
from app.connectors.assisted.connector import AssistedConnector
from app.connectors.devto.connector import DevtoConnector
from app.connectors.discourse.connector import DiscourseConnector
from app.connectors.registry import register_connector
from app.db.models import (
    AlertModel,
    CertificationModel,
    ConnectorModel,
    DestinationModel,
    PassportModel,
)
from app.queue.worker import process_single_job
from mockhub.app import GLOBAL_CHAOS, STORE
from mockhub.app import app as mockhub_app


class MockHubSyncTransport(httpx.BaseTransport):
    """Sync transport routing requests directly to mockhub_app."""

    def __init__(self, app):
        self.client = TestClient(app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url_path = request.url.raw_path.decode("utf-8")
        headers = dict(request.headers)
        headers.pop("host", None)
        return self.client.request(
            method=request.method,
            url=url_path,
            headers=headers,
            content=request.content,
        )


@pytest.fixture(autouse=True)
def intercept_mockhub_network(monkeypatch):
    """Routes httpx requests directed to mockhub in-process to mockhub_app."""
    STORE.clear()
    GLOBAL_CHAOS["fault"] = None
    mock_client = TestClient(mockhub_app)
    orig_send = httpx.Client.send

    def patched_send(self, request, *args, **kwargs):
        url_str = str(request.url)
        if "8010" in url_str or "mockhub" in url_str:
            url_path = request.url.raw_path.decode("utf-8")
            headers = dict(request.headers)
            headers.pop("host", None)
            return mock_client.request(
                method=request.method,
                url=url_path,
                headers=headers,
                content=request.content,
            )
        return orig_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", patched_send)
    yield


@pytest.fixture
def registered_connectors():
    register_connector("discourse", DiscourseConnector())
    register_connector("devto", DevtoConnector())
    register_connector("assisted", AssistedConnector())


def test_discourse_7_step_certification_success(db_session, registered_connectors):
    """Asserts 7-step certification runs to completion, bundles evidence, and promotes to L4."""
    conn = ConnectorModel(key="discourse", enabled=True, version="1.0.0")
    db_session.add(conn)
    dest = DestinationModel(
        id="dest_cert_discourse_01",
        name="Discourse Community",
        url="http://localhost:8010",
        platform_key="discourse",
        connector_key="discourse",
        level="L0",
        status="active",
    )
    db_session.add(dest)
    passport = PassportModel(destination_id=dest.id, level="L0", health_score=100.0)
    db_session.add(passport)
    db_session.commit()

    # Execute 7-step certification
    result = run_certification(db_session, dest.id)
    assert result["status"] == "passed"
    assert result["level"] == "L4"
    assert "certification_pack/discourse/" in result["evidence_uri"]
    assert len(result["steps"]) == 7

    # Verify DB state
    db_session.refresh(passport)
    db_session.refresh(dest)
    assert passport.level == "L4"
    assert dest.level == "L4"
    assert passport.last_certified_at is not None
    assert passport.expires_at is not None
    assert passport.schema_fingerprint is not None

    # Verify certification audit row
    cert_row = db_session.query(CertificationModel).filter_by(destination_id=dest.id).first()
    assert cert_row is not None
    assert cert_row.passed is True


def test_assisted_connector_certification(db_session, registered_connectors):
    """Asserts Assisted connector certifies cleanly and promotes to L1."""
    conn = ConnectorModel(key="assisted", enabled=True, version="1.0.0")
    db_session.add(conn)
    dest = DestinationModel(
        id="dest_cert_assisted_01",
        name="Manual Forum",
        url="https://manual.forum.org",
        platform_key="assisted",
        connector_key="assisted",
        level="L0",
        status="active",
        automation_allowed=False,
    )
    db_session.add(dest)
    passport = PassportModel(destination_id=dest.id, level="L0", health_score=100.0)
    db_session.add(passport)
    db_session.commit()

    result = run_certification(db_session, dest.id)
    assert result["status"] == "passed"
    assert result["level"] == "L1"


def test_drift_canary_demotes_on_renamed_field(db_session, registered_connectors):
    """Asserts certification fails, demotes to L0, and writes Alert when platform renames a field."""
    conn = ConnectorModel(key="devto", enabled=True, version="1.0.0")
    db_session.add(conn)
    dest = DestinationModel(
        id="dest_cert_drift_01",
        name="Dev.to API Test",
        url="http://localhost:8010",
        platform_key="devto",
        connector_key="devto",
        level="L3",
        status="active",
    )
    db_session.add(dest)
    passport = PassportModel(destination_id=dest.id, level="L3", health_score=100.0)
    db_session.add(passport)
    db_session.commit()

    # Trigger upstream platform drift in mockhub (url -> live_link)
    GLOBAL_CHAOS["fault"] = "rename_field"

    result = run_certification(db_session, dest.id)
    assert result["status"] == "failed"
    assert "Drift Canary detected field mismatch" in result["reason"]

    # Verify destination was auto-demoted to L0 and status='demoted'
    db_session.refresh(dest)
    db_session.refresh(passport)
    assert dest.level == "L0"
    assert dest.status == "demoted"
    assert passport.level == "L0"
    assert passport.health_score <= 50.0

    # Verify Alert row was written
    alert = db_session.query(AlertModel).filter_by(destination_id=dest.id).first()
    assert alert is not None
    assert alert.kind == "CERT_DRIFT_DETECTED"


def test_certify_api_endpoint_and_job_worker(client, db_session, registered_connectors):
    """Asserts POST /api/v1/destinations/{id}/certify triggers worker job and promotes Passport."""
    conn = ConnectorModel(key="discourse", enabled=True, version="1.0.0")
    db_session.add(conn)
    dest = DestinationModel(
        id="dest_api_cert_01",
        name="Discourse Async Target",
        url="http://localhost:8010",
        platform_key="discourse",
        connector_key="discourse",
        level="L0",
        status="active",
    )
    db_session.add(dest)
    passport = PassportModel(destination_id=dest.id, level="L0", health_score=100.0)
    db_session.add(passport)
    db_session.commit()

    # 1. Trigger certification via API endpoint
    res = client.post(f"/api/v1/destinations/{dest.id}/certify")
    assert res.status_code == 202
    job_id = res.json()["job_id"]
    assert job_id is not None

    # 2. Worker executes certify job
    process_single_job(job_id, db=db_session)

    # 3. Query Passport via API
    res_pass = client.get(f"/api/v1/destinations/{dest.id}/passport")
    assert res_pass.status_code == 200
    pass_data = res_pass.json()
    assert pass_data["level"] == "L4"
    assert pass_data["health_score"] == 100.0
    assert pass_data["schema_fingerprint"] is not None
    assert pass_data["evidence_uri"] is not None
