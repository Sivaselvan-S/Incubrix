"""Tests for Base Connector contract, manifest loading, error mapping, and runtime router."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.connectors.base import BaseConnector, ConnectorManifest
from app.connectors.registry import register_connector
from app.db.models import ConnectorModel


class DummyMockConnector(BaseConnector):
    """Dummy connector for testing runtime router dispatch and error mapping."""

    def __init__(self, key: str = "mock_test"):
        self.manifest = ConnectorManifest(
            key=key,
            version="1.0.0",
            tier="native",
            error_map={"418": "PLATFORM_CONTENT_REJECTED"},
        )

    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {"ok": True, "violations": []}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "platform_post_id": "mock_post_999",
            "live_url": "https://mock.platform/posts/999",
            "status": "published",
        }

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": "published",
            "live_url": f"https://mock.platform/posts/{platform_post_id}",
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {"deleted": True}

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
        since=None,
    ) -> dict[str, Any]:
        return {"views": 100, "likes": 10, "comments": 2, "shares": 1, "clicks": 5}


@pytest.fixture(autouse=True)
def setup_dummy_connector():
    """Ensures dummy connector is registered for runtime router tests."""
    connector = DummyMockConnector("mock_test")
    register_connector("mock_test", connector)
    return connector


def test_manifest_error_mapping():
    """Asserts HTTP status mapping adheres to standard contract and respects custom overrides."""
    connector = DummyMockConnector("test_err_mapper")

    # Standard status mappings
    assert connector.map_http_status_to_error(400)["error"]["code"] == "DEST_SPEC_VIOLATION"
    assert connector.map_http_status_to_error(401)["error"]["code"] == "CONNECTION_AUTH_EXPIRED"
    assert connector.map_http_status_to_error(403)["error"]["code"] == "CONNECTION_AUTH_EXPIRED"
    assert connector.map_http_status_to_error(422)["error"]["code"] == "PLATFORM_CONTENT_REJECTED"
    assert connector.map_http_status_to_error(429)["error"]["code"] == "PLATFORM_RATE_LIMIT"
    assert connector.map_http_status_to_error(500)["error"]["code"] == "PLATFORM_UNAVAILABLE"
    assert connector.map_http_status_to_error(503)["error"]["code"] == "PLATFORM_UNAVAILABLE"

    # Custom manifest override (418 -> PLATFORM_CONTENT_REJECTED)
    assert connector.map_http_status_to_error(418)["error"]["code"] == "PLATFORM_CONTENT_REJECTED"


def test_runtime_router_validate(client: TestClient):
    """Asserts POST /connector/v1/{key}/validate dispatches correctly."""
    res = client.post(
        "/connector/v1/mock_test/validate",
        json={"rendition": {"title": "Hello"}, "destination": {}, "connection": {}},
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True, "violations": []}


def test_runtime_router_publish(client: TestClient):
    """Asserts POST /connector/v1/{key}/publish requires idempotency_key and dispatches."""
    # 1. Missing idempotency key fails with 400
    res_err = client.post(
        "/connector/v1/mock_test/publish",
        json={"rendition": {"title": "Hello"}},
    )
    assert res_err.status_code == 400
    assert res_err.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Valid publish succeeds
    res_ok = client.post(
        "/connector/v1/mock_test/publish",
        json={
            "rendition": {"title": "Hello"},
            "idempotency_key": "idem_12345",
        },
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["platform_post_id"] == "mock_post_999"
    assert data["status"] == "published"


def test_runtime_router_get_status_and_delete(client: TestClient):
    """Asserts get_status and delete methods work with platform_post_id."""
    res_status = client.post(
        "/connector/v1/mock_test/get_status",
        json={"platform_post_id": "mock_post_999"},
    )
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "published"

    res_del = client.post(
        "/connector/v1/mock_test/delete",
        json={"platform_post_id": "mock_post_999"},
    )
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True


def test_runtime_router_metrics(client: TestClient):
    """Asserts fetch_metrics returns engagement metrics."""
    res = client.post(
        "/connector/v1/mock_test/fetch_metrics",
        json={"platform_post_id": "mock_post_999"},
    )
    assert res.status_code == 200
    assert res.json()["views"] == 100


def test_runtime_router_kill_switch_and_circuit_breaker(client: TestClient, db_session: Session):
    """Asserts kill switch (enabled=false) and circuit breaker block execution."""
    conn_record = ConnectorModel(
        key="mock_test", version="1.0.0", enabled=True, consecutive_failures=0
    )
    db_session.add(conn_record)
    db_session.commit()

    # Kill switch disabled
    conn_record.enabled = False
    db_session.commit()
    res_disabled = client.post(
        "/connector/v1/mock_test/validate",
        json={"rendition": {}},
    )
    assert res_disabled.status_code == 503
    assert res_disabled.json()["error"]["code"] == "CONNECTOR_DISABLED"

    # Circuit breaker open
    conn_record.enabled = True
    conn_record.consecutive_failures = 5
    db_session.commit()
    res_circuit = client.post(
        "/connector/v1/mock_test/validate",
        json={"rendition": {}},
    )
    assert res_circuit.status_code == 503
    assert res_circuit.json()["error"]["code"] == "PLATFORM_UNAVAILABLE"


def test_runtime_router_unknown_connector_and_method(client: TestClient):
    """Asserts 404 for unknown connector and 400 for unknown method."""
    res_unknown_conn = client.post(
        "/connector/v1/non_existent_key/validate",
        json={},
    )
    assert res_unknown_conn.status_code == 404
    assert res_unknown_conn.json()["error"]["code"] == "CONNECTOR_NOT_FOUND"

    res_unknown_method = client.post(
        "/connector/v1/mock_test/unsupported_method",
        json={},
    )
    assert res_unknown_method.status_code == 400
    assert res_unknown_method.json()["error"]["code"] == "VALIDATION_ERROR"
