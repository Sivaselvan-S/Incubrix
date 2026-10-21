"""Tests for Chaos Mock Hub and Core Connectors (discourse, devto, webhook_hmac, assisted)."""

import httpx
import pytest
from starlette.testclient import TestClient

from app.connectors.assisted.connector import AssistedConnector
from app.connectors.devto.connector import DevtoConnector
from app.connectors.discourse.connector import DiscourseConnector
from app.connectors.webhook_hmac.connector import WebhookHmacConnector
from mockhub.app import STORE
from mockhub.app import app as mockhub_app


class MockHubTransport(httpx.BaseTransport):
    """Synchronous transport adapter that delegates HTTP calls to mockhub_app via TestClient."""

    def __init__(self, app):
        self.test_client = TestClient(app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url_path = request.url.raw_path.decode("utf-8")
        headers = dict(request.headers)
        headers.pop("host", None)

        res = self.test_client.request(
            method=request.method,
            url=url_path,
            headers=headers,
            content=request.content,
        )
        return res


@pytest.fixture(autouse=True)
def mockhub_client_interceptor(monkeypatch):
    """Intercepts httpx calls directed to MockHub URL and routes them in-process to mockhub_app."""
    STORE.clear()
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


def test_mockhub_health():
    """Asserts mockhub health check is alive and responds."""
    client = TestClient(mockhub_app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_discourse_connector_lifecycle():
    """Asserts Discourse connector publish -> get_status -> delete lifecycle."""
    connector = DiscourseConnector()
    dest = {"url": "http://localhost:8010", "category": "tech"}
    conn = {"api_key": "valid_discourse_key", "api_username": "admin"}
    rendition = {"title": "Discourse Discussion Topic", "body": "Explaining consensus algorithms."}

    # 1. Validate
    v = connector.validate(rendition, dest, conn)
    assert v["ok"] is True

    # 2. Publish
    res = connector.publish(rendition, dest, conn, idempotency_key="discourse_idem_1")
    assert res["status"] == "published"
    post_id = res["platform_post_id"]
    assert post_id is not None
    assert "t/42/" in res["live_url"]

    # 3. Get Status
    status_res = connector.get_status(post_id, conn)
    assert status_res["status"] == "live"

    # 4. Delete
    del_res = connector.delete(post_id, conn)
    assert del_res["deleted"] is True

    # 5. Get Status after delete
    status_after = connector.get_status(post_id, conn)
    assert status_after["status"] == "deleted"


def test_discourse_chaos_faults():
    """Asserts Discourse connector handles 422, 429, and 401 correctly."""
    connector = DiscourseConnector()
    dest = {"url": "http://localhost:8010"}
    rendition = {"title": "Chaos Test", "body": "Body"}

    # 422 Content Rejected
    with pytest.raises(ValueError, match="PLATFORM_CONTENT_REJECTED"):
        connector.publish(
            rendition,
            dest,
            {"api_key": "key", "x_chaos": "422"},
            idempotency_key="discourse_chaos_422",
        )

    # 429 Rate Limit
    with pytest.raises(ValueError, match="PLATFORM_RATE_LIMIT"):
        connector.publish(
            rendition,
            dest,
            {"api_key": "key", "x_chaos": "429"},
            idempotency_key="discourse_chaos_429",
        )

    # 401 Expired Auth
    with pytest.raises(ValueError, match="CONNECTION_AUTH_EXPIRED"):
        connector.publish(
            rendition,
            dest,
            {"api_key": "key", "x_chaos": "401"},
            idempotency_key="discourse_chaos_401",
        )


def test_devto_connector_lifecycle_and_unpublish():
    """Asserts Dev.to connector publish -> get_status -> honest unpublish deletion."""
    connector = DevtoConnector()
    dest = {"url": "http://localhost:8010"}
    conn = {"api_key": "devto_mock_key"}
    rendition = {
        "title": "Async IO Deep Dive",
        "body": "Understanding the event loop in Python 3.13.",
        "tags": ["python", "asyncio", "backend"],
        "canonical_url": "https://incubrix.com/blog/asyncio",
    }

    # 1. Validate
    v = connector.validate(rendition, dest, conn)
    assert v["ok"] is True

    # 2. Publish
    res = connector.publish(rendition, dest, conn, idempotency_key="devto_idem_1")
    assert res["status"] == "published"
    post_id = res["platform_post_id"]
    assert post_id is not None
    assert res["live_url"] == "https://incubrix.com/blog/asyncio"

    # 3. Get Status
    status_res = connector.get_status(post_id, conn)
    assert status_res["status"] == "live"

    # 4. Delete (Unpublish)
    del_res = connector.delete(post_id, conn)
    assert del_res["deleted"] is True
    assert del_res["method"] == "unpublish"

    # 5. Get Status after unpublish
    status_after = connector.get_status(post_id, conn)
    assert status_after["status"] == "unpublished"


def test_webhook_hmac_connector():
    """Asserts Webhook HMAC bridge connector signs payload and handles partner revocation."""
    connector = WebhookHmacConnector()
    dest = {"url": "http://localhost:8010/partner/webhook", "id": "partner_dest_1"}
    conn = {"secret": "incubrix_partner_secret"}
    rendition = {"title": "Partner Broadcast", "body": "Distributed event message."}

    # 1. Valid signed publish succeeds
    res = connector.publish(rendition, dest, conn, idempotency_key="wh_idem_1")
    assert res["status"] == "published"
    assert "evt_" in res["platform_post_id"]

    # 2. Partner revoking permission (403) mapped to CONNECTION_AUTH_EXPIRED
    with pytest.raises(ValueError, match="CONNECTION_AUTH_EXPIRED"):
        connector.publish(
            rendition,
            dest,
            {"secret": "incubrix_partner_secret", "x_chaos": "403"},
            idempotency_key="wh_chaos_403",
        )


def test_assisted_connector_pack_builder():
    """Asserts Assisted connector builds complete pack with rule checklists."""
    connector = AssistedConnector()
    dest = {
        "url": "https://manual.community.org/submit",
        "name": "Strict Manual Forum",
        "disclosure_required": True,
        "self_promo_allowed": False,
    }
    rendition = {
        "title": "Manual Submission Item",
        "body": "Carefully formatted manual report.",
        "media": ["https://s3.example.com/slide1.png"],
    }

    pack = connector.build_assist_pack(rendition, dest)
    assert pack["deep_link"] == "https://manual.community.org/submit"
    assert "Manual Submission Item" in pack["caption"]
    assert len(pack["files"]) == 1
    assert any("AI transparency disclosure" in c for c in pack["checklist"])
    assert any("zero direct promotional links" in c for c in pack["checklist"])

    # Publish returns pack directly
    pub_res = connector.publish(rendition, dest, {}, idempotency_key="assist_1")
    assert pub_res["status"] == "assisted_pack_ready"
    assert "pack" in pub_res
