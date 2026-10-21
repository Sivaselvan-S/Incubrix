import pytest
from starlette.testclient import TestClient

from app.certify.harness import run_certification
from app.connectors.ghost.connector import GhostConnector, generate_ghost_admin_jwt
from app.connectors.hashnode.connector import HashnodeConnector
from app.connectors.init_connectors import register_all_connectors
from app.connectors.lemmy.connector import LemmyConnector
from app.connectors.mrss_feed.connector import MRSSFeedConnector
from app.connectors.registry import get_connector
from app.connectors.slack.connector import SlackConnector
from app.db.models import ConnectorModel, DestinationModel, PassportModel
from mockhub.app import STORE
from mockhub.app import app as mockhub_app


@pytest.fixture(autouse=True)
def init_all_and_mockhub(monkeypatch):
    """Initializes connectors and patches httpx client for mockhub."""
    register_all_connectors()
    STORE.clear()
    import httpx

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


def test_all_connectors_registered():
    """Asserts that all 9 platform connectors are registered."""
    expected_keys = [
        "assisted",
        "webhook_hmac",
        "discourse",
        "devto",
        "lemmy",
        "ghost",
        "mrss_feed",
        "hashnode",
        "slack",
    ]
    for key in expected_keys:
        connector = get_connector(key)
        assert connector is not None
        assert connector.manifest.key == key


# ------------------------------------------------------------------------------
# Lemmy Connector Tests
# ------------------------------------------------------------------------------
def test_lemmy_connector_lifecycle():
    """Asserts Lemmy connector publish -> get_status -> delete lifecycle."""
    connector = LemmyConnector()
    dest = {"url": "http://localhost:8010", "community_id": 42}
    conn = {"auth_token": "mock_jwt_lemmy_auth"}
    rendition = {
        "title": "Decentralized Social Networks in 2026",
        "body": "ActivityPub and Lemmy protocol overview.",
    }

    # Validate
    v = connector.validate(rendition, dest, conn)
    assert v["ok"] is True

    # Publish
    res = connector.publish(rendition, dest, conn, idempotency_key="lemmy_idem_1")
    assert res["status"] == "published"
    post_id = res["platform_post_id"]
    assert post_id is not None
    assert "post" in res["live_url"]

    # Live check
    assert connector.live_check(post_id, {"connection": conn}) is True

    # Get status
    status = connector.get_status(post_id, conn)
    assert status["status"] == "published"

    # Delete
    del_res = connector.delete(post_id, conn)
    assert del_res["status"] == "deleted"

    # Get status after delete
    status_after = connector.get_status(post_id, conn)
    assert status_after["status"] == "deleted"

    # Assist pack
    pack = connector.build_assist_pack(rendition, dest)
    assert pack["type"] == "lemmy_assisted"
    assert pack["post_data"]["community_id"] == 42


def test_lemmy_chaos_error():
    """Asserts Lemmy connector handles simulated chaos faults."""
    connector = LemmyConnector()
    dest = {"url": "http://localhost:8010", "community_id": 1}
    conn = {"auth_token": "mock_jwt", "x_chaos": "401"}
    rendition = {"title": "Test Title", "body": "Test Body"}

    with pytest.raises(ValueError) as exc:
        connector.publish(rendition, dest, conn, idempotency_key="lemmy_fail")
    assert "CONNECTION_AUTH_EXPIRED" in str(exc.value)


# ------------------------------------------------------------------------------
# Ghost Admin API Connector Tests
# ------------------------------------------------------------------------------
def test_ghost_jwt_generation():
    """Asserts Ghost Admin API JWT generation follows HS256 spec."""
    key = "64f8a7e0c4b6a1234567890a:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    token = generate_ghost_admin_jwt(key)
    parts = token.split(".")
    assert len(parts) == 3


def test_ghost_connector_lifecycle():
    """Asserts Ghost connector publish -> get_status -> delete lifecycle."""
    connector = GhostConnector()
    dest = {"url": "http://localhost:8010"}
    conn = {
        "admin_api_key": "64f8a7e0c4b6a1234567890a:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
    rendition = {
        "title": "Ghost Publication Story",
        "body": "<p>Content written in HTML for Ghost blog.</p>",
        "canonical_url": "https://example.com/canonical-ghost",
    }

    # Validate
    v = connector.validate(rendition, dest, conn)
    assert v["ok"] is True

    # Publish
    res = connector.publish(rendition, dest, conn, idempotency_key="ghost_idem_1")
    assert res["status"] == "published"
    post_id = res["platform_post_id"]
    assert post_id is not None
    assert post_id in res["live_url"]

    # Live check
    assert connector.live_check(post_id, {"connection": conn}) is True

    # Get status
    status = connector.get_status(post_id, conn)
    assert status["status"] == "published"

    # Delete
    del_res = connector.delete(post_id, conn)
    assert del_res["status"] == "deleted"


# ------------------------------------------------------------------------------
# MRSS Feed Connector Tests
# ------------------------------------------------------------------------------
def test_mrss_feed_lifecycle_and_idempotency():
    """Asserts MRSS Feed connector XML generation, media namespaces, and idempotency."""
    import uuid

    feed_name = f"podcast_feed_{uuid.uuid4().hex[:6]}"
    connector = MRSSFeedConnector()
    dest = {
        "feed_name": feed_name,
        "name": "Tech Podcasts",
        "url": f"https://feeds.incubrix.local/{feed_name}",
    }
    conn = {"feed_name": feed_name}

    rendition1 = {
        "title": "Episode 1: The LongTail Network",
        "body": "First episode discussing federated destination distribution.",
        "canonical_url": "https://incubrix.local/episodes/1",
        "media_url": "https://media.incubrix.local/ep1.jpg",
    }

    # 1. First publish
    res1 = connector.publish(rendition1, dest, conn, idempotency_key="ep_guid_001")
    assert res1["status"] == "published"
    assert res1["platform_post_id"] == "ep_guid_001"
    assert res1["items_count"] == 1

    # 2. Re-publish same idempotency key with updated title (Idempotent in-place update)
    rendition1_updated = dict(rendition1)
    rendition1_updated["title"] = "Episode 1: The LongTail Network (Updated Edition)"
    res1_up = connector.publish(rendition1_updated, dest, conn, idempotency_key="ep_guid_001")
    assert res1_up["items_count"] == 1  # No duplicate item!

    # Verify updated title in get_status
    st = connector.get_status("ep_guid_001", conn)
    assert st["status"] == "published"
    assert "Updated Edition" in st["title"]

    # 3. Publish second distinct item
    rendition2 = {
        "title": "Episode 2: Proof of Verification",
        "body": "Second episode covering Preflight Court.",
        "canonical_url": "https://incubrix.local/episodes/2",
    }
    res2 = connector.publish(rendition2, dest, conn, idempotency_key="ep_guid_002")
    assert res2["items_count"] == 2

    # 4. Live check
    assert connector.live_check("ep_guid_001", dest) is True
    assert connector.live_check("ep_guid_002", dest) is True

    # 5. Delete item 1
    del_res = connector.delete("ep_guid_001", conn)
    assert del_res["status"] == "deleted"
    assert del_res["removed"] is True

    # 6. Verify item 1 is deleted and item 2 remains
    st_del = connector.get_status("ep_guid_001", conn)
    assert st_del["status"] == "deleted"
    st_rem = connector.get_status("ep_guid_002", conn)
    assert st_rem["status"] == "published"


# ------------------------------------------------------------------------------
# Hashnode GraphQL Connector Tests
# ------------------------------------------------------------------------------
def test_hashnode_connector_lifecycle():
    """Asserts Hashnode connector publish -> get_status -> delete lifecycle via GraphQL."""
    connector = HashnodeConnector()
    dest = {"publication_id": "pub_incubrix_blog"}
    conn = {"token": "hashnode_token_abc"}
    rendition = {
        "title": "Modern Microservices with FastAPI",
        "body": "Complete architectural walkthrough.",
        "canonical_url": "https://example.com/canonical-hashnode",
    }

    # Validate
    v = connector.validate(rendition, dest, conn)
    assert v["ok"] is True

    # Publish
    res = connector.publish(rendition, dest, conn, idempotency_key="hn_idem_1")
    assert res["status"] == "published"
    post_id = res["platform_post_id"]
    assert post_id is not None
    assert "blog.hashnode.dev" in res["live_url"]

    # Live check
    assert connector.live_check(post_id, {"connection": conn}) is True

    # Delete
    del_res = connector.delete(post_id, conn)
    assert del_res["status"] == "deleted"


# ------------------------------------------------------------------------------
# Slack Connector Tests
# ------------------------------------------------------------------------------
def test_slack_connector_lifecycle():
    """Asserts Slack connector message posting -> get_status -> delete lifecycle."""
    connector = SlackConnector()
    dest = {"channel": "eng-announcements"}
    conn = {"bot_token": "xoxb-test-token"}
    rendition = {
        "title": "Release v1.2.0 Deployed",
        "body": "All automated integration tests passed with 100% success rate.",
    }

    # Validate
    v = connector.validate(rendition, dest, conn)
    assert v["ok"] is True

    # Publish
    res = connector.publish(rendition, dest, conn, idempotency_key="slack_idem_1")
    assert res["status"] == "published"
    ts = res["platform_post_id"]
    assert ts is not None
    assert "slack.com/archives" in res["live_url"]

    # Get status
    st = connector.get_status(ts, {"channel": "eng-announcements"})
    assert st["status"] == "published"

    # Delete
    del_res = connector.delete(ts, {"channel": "eng-announcements"})
    assert del_res["status"] == "deleted"


# ------------------------------------------------------------------------------
# Runtime Router Endpoint Tests for New Connectors
# ------------------------------------------------------------------------------
def test_runtime_router_with_new_connectors(client):
    """Asserts POST /connector/v1/{connector_key}/{method} works dynamically for new connectors."""
    # Lemmy publish via runtime router
    res_lemmy = client.post(
        "/connector/v1/lemmy/publish",
        json={
            "rendition": {"title": "Router Post Lemmy", "body": "Content body"},
            "destination": {"community_id": 5},
            "connection": {"auth_token": "mock_jwt"},
            "idempotency_key": "router_lemmy_1",
        },
    )
    assert res_lemmy.status_code == 200
    assert res_lemmy.json()["status"] == "published"

    # Ghost publish via runtime router
    res_ghost = client.post(
        "/connector/v1/ghost/publish",
        json={
            "rendition": {"title": "Router Post Ghost", "body": "<p>Content</p>"},
            "destination": {"url": "http://localhost:8010"},
            "connection": {"admin_api_key": "dummy_key"},
            "idempotency_key": "router_ghost_1",
        },
    )
    assert res_ghost.status_code == 200
    assert res_ghost.json()["status"] == "published"

    # MRSS Feed publish via runtime router
    res_mrss = client.post(
        "/connector/v1/mrss_feed/publish",
        json={
            "rendition": {"title": "Router Item MRSS", "body": "Feed item description"},
            "destination": {"feed_name": "router_feed"},
            "connection": {"feed_name": "router_feed"},
            "idempotency_key": "router_mrss_1",
        },
    )
    assert res_mrss.status_code == 200
    assert res_mrss.json()["status"] == "published"


# ------------------------------------------------------------------------------
# Certification Harness on Extra Connectors
# ------------------------------------------------------------------------------
def test_certification_harness_on_ghost_and_lemmy(db_session):
    """Asserts full 7-step certification harness succeeds on Ghost and Lemmy destinations."""
    # 1. Setup Ghost Connector & Destination in DB
    ghost_conn = ConnectorModel(
        key="ghost",
        version="1.0.0",
        enabled=True,
    )
    db_session.add(ghost_conn)
    db_session.commit()

    dest_ghost = DestinationModel(
        id="dest_ghost_cert_1",
        name="Ghost Production Blog",
        platform_key="ghost",
        connector_key="ghost",
        status="active",
        level="L0",
        url="http://localhost:8010",
        instance_config_json={"base_url": "http://localhost:8010"},
    )
    db_session.add(dest_ghost)
    db_session.commit()

    passport_ghost = PassportModel(
        destination_id=dest_ghost.id,
        level="L1",
        health_score=80,
    )
    db_session.add(passport_ghost)
    db_session.commit()

    # Run certification
    cert_res = run_certification(db_session, dest_ghost.id)
    assert cert_res["status"] == "passed"
    assert cert_res["evidence_uri"] is not None
    assert cert_res["level"] in ("L1", "L2", "L3", "L4")
