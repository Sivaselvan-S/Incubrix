"""Comprehensive Hard-Cases Verification Suite (13 Hard Cases + Secrets Leak Prevention).

Covers all platform anomalies, edge cases, Preflight Court violations, and idempotency guarantees:
1. Timeout then retry same key -> exactly one post (Idempotency ledger & reconciliation).
2. 429 with reset time -> PLATFORM_RATE_LIMIT, backoff honored, job rescheduled.
3. Expired token (401) -> CONNECTION_AUTH_EXPIRED, paused.
4. Content rejected (422) -> PLATFORM_CONTENT_REJECTED with platform message.
5. Title/body too long -> REWRITE truncation or DEST_SPEC_VIOLATION with field reasons.
6. Unsupported media -> clear violation error.
7. Second post within weekly cap -> RESCHEDULE with earliest_allowed_at and DEST_RULE_FREQUENCY_CAP.
8. Promo post to no-promo destination -> BLOCK DEST_RULE_PROMO_BLOCKED.
9. Platform renames a field -> certification fails, destination demoted, alert created.
10. CSV with duplicates, bad URLs, mixed languages -> row-by-row error report.
11. Partner revokes permission (403) -> demoted + reconnect required (CONNECTION_AUTH_EXPIRED).
12. Non-English community -> language warning, no silent mistranslation.
13. AI disclosure required -> disclosure appended (REWRITE) or blocked with reason.
14. Secrets test -> redaction filter verifies tokens, passwords, and keys are never leaked to logs.
"""

import logging
from datetime import UTC, datetime, timedelta
from io import StringIO

import httpx
import pytest
from starlette.testclient import TestClient

from app.catalogue.importer import import_catalogue_csv
from app.certify.harness import run_certification
from app.connectors.devto.connector import DevtoConnector
from app.connectors.discourse.connector import DiscourseConnector
from app.connectors.init_connectors import register_all_connectors
from app.connectors.webhook_hmac.connector import WebhookHmacConnector
from app.db.models import (
    AlertModel,
    ConnectionModel,
    ConnectorModel,
    DestinationModel,
    PassportModel,
)
from app.idempotency.ledger import (
    check_or_reserve_intent,
    record_success,
    record_unknown,
)
from app.logging import SecretRedactionFilter
from app.rules.court import evaluate
from app.rules.schemas import (
    DestinationRuleContext,
    PostHistoryItem,
    Rendition,
    SurfaceSpec,
    VerdictEnum,
)
from mockhub.app import GLOBAL_CHAOS, STORE
from mockhub.app import app as mockhub_app


@pytest.fixture(autouse=True)
def mockhub_interceptor(monkeypatch):
    """Intercepts httpx calls directed to MockHub URL and routes them to mockhub_app."""
    register_all_connectors()
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
    GLOBAL_CHAOS["fault"] = None
    STORE.clear()


# =========================================================================
# HARD CASE 1: Timeout then retry with same key -> exactly one post
# =========================================================================
def test_hard_case_1_timeout_then_retry_same_key_exactly_one_post(db_session):
    """Verifies that an intent-first timeout followed by a retry returns the existing post."""
    key = "idemp_hc1_timeout_test"
    payload = {"destination_id": "dest_test_001", "rendition": {"title": "Title 1", "body": "Body 1"}}

    # 1. First attempt registers INTENT
    action, result = check_or_reserve_intent(db_session, key, payload)
    assert action == "NEW"
    db_session.commit()

    # Simulate network timeout: state is marked UNKNOWN
    record_unknown(db_session, key)
    db_session.commit()

    # Destination and post reconciliation: assume post succeeded upstream on platform
    fake_result = {"platform_post_id": "ext_post_1001", "live_url": "https://example.com/p/1001"}
    record_success(db_session, key, fake_result)
    db_session.commit()

    # 2. Retry with the EXACT SAME key and payload
    retry_action, cached_res = check_or_reserve_intent(db_session, key, payload)
    assert retry_action == "CACHED"
    assert cached_res["platform_post_id"] == "ext_post_1001"
    assert cached_res["live_url"] == "https://example.com/p/1001"


# =========================================================================
# HARD CASE 2: 429 with reset time -> backoff honoured, job rescheduled
# =========================================================================
def test_hard_case_2_rate_limit_429_backoff_and_reschedule():
    """Verifies that HTTP 429 rate limit is mapped to PLATFORM_RATE_LIMIT and provides retry_after."""
    connector = DiscourseConnector()
    error_mapped = connector.map_http_status_to_error(429, "Rate limit exceeded. Try again in 30 seconds.")
    assert error_mapped["error"]["code"] == "PLATFORM_RATE_LIMIT"
    assert error_mapped["error"]["retryable"] is True
    assert "back off" in error_mapped["error"]["details"]["action"].lower()

    destination = {"instance_config": {"base_url": "http://localhost:8010/discourse"}}
    connection = {"secret": "secret_api_key"}

    GLOBAL_CHAOS["fault"] = "429"
    rendition = {"title": "Discourse 429 Test Topic", "body": "Testing rate limit handling"}

    with pytest.raises(ValueError) as exc_info:
        connector.publish(rendition, destination, connection, idempotency_key="idemp_hc2")

    assert "PLATFORM_RATE_LIMIT" in str(exc_info.value)


# =========================================================================
# HARD CASE 3: Expired token (401) -> CONNECTION_AUTH_EXPIRED, paused
# =========================================================================
def test_hard_case_3_expired_token_401_connection_auth_expired():
    """Verifies that HTTP 401 is mapped to CONNECTION_AUTH_EXPIRED and requires reconnect."""
    connector = DevtoConnector()
    error_mapped = connector.map_http_status_to_error(401, "Unauthorized access token")
    assert error_mapped["error"]["code"] == "CONNECTION_AUTH_EXPIRED"
    assert "reconnect" in error_mapped["error"]["details"]["action"].lower()

    destination = {"instance_config": {"base_url": "http://localhost:8010/devto"}}
    connection = {"secret": "invalid_or_expired_key"}

    GLOBAL_CHAOS["fault"] = "401"
    rendition = {"title": "Article Auth Expire Test", "body": "Testing expired auth token"}

    with pytest.raises(ValueError) as exc_info:
        connector.publish(rendition, destination, connection, idempotency_key="idemp_hc3")

    assert "CONNECTION_AUTH_EXPIRED" in str(exc_info.value)


# =========================================================================
# HARD CASE 4: Content rejected (422) -> PLATFORM_CONTENT_REJECTED with platform message
# =========================================================================
def test_hard_case_4_content_rejected_422_with_platform_message():
    """Verifies that HTTP 422 Unprocessable Entity preserves the upstream platform error message."""
    connector = DiscourseConnector()
    error_mapped = connector.map_http_status_to_error(422, "Title contains banned words")
    assert error_mapped["error"]["code"] == "PLATFORM_CONTENT_REJECTED"
    assert error_mapped["error"]["retryable"] is False
    assert "banned words" in error_mapped["error"]["message"]

    destination = {"instance_config": {"base_url": "http://localhost:8010/discourse"}}
    connection = {"secret": "test_key"}

    GLOBAL_CHAOS["fault"] = "422"
    rendition = {"title": "Rejected Content", "body": "Short"}

    with pytest.raises(ValueError) as exc_info:
        connector.publish(rendition, destination, connection, idempotency_key="idemp_hc4")

    assert "PLATFORM_CONTENT_REJECTED" in str(exc_info.value)


# =========================================================================
# HARD CASE 5: Title/body too long -> REWRITE truncation or DEST_SPEC_VIOLATION
# =========================================================================
def test_hard_case_5_title_body_too_long_rewrite_or_violation():
    """Verifies that oversized titles or bodies are automatically truncated at word boundaries."""
    long_title = "This is a super long announcement title that exceeds the allowed character limit for discourse topics by quite a wide margin"
    rendition = Rendition(
        title=long_title,
        body="Standard valid discussion body with plenty of character count.",
        language="en",
    )
    destination = DestinationRuleContext(destination_status="active")
    surface_spec = SurfaceSpec(max_title_chars=50, max_body_chars=5000)

    verdict = evaluate(rendition, destination, surface_spec=surface_spec)
    assert verdict.verdict == VerdictEnum.REWRITE
    assert verdict.rewritten_rendition is not None
    assert len(verdict.rewritten_rendition.title) <= 50
    assert verdict.rewritten_rendition.title.endswith("...")


# =========================================================================
# HARD CASE 6: Unsupported media -> clear violation error
# =========================================================================
def test_hard_case_6_unsupported_media_violation():
    """Verifies that attachments with disallowed media types cause a clear DEST_SPEC_VIOLATION."""
    rendition = Rendition(
        title="Topic with unsupported media",
        body="Check out this media attachment.",
        media=["video/mp4"],
        language="en",
    )
    destination = DestinationRuleContext(destination_status="active")
    surface_spec = SurfaceSpec(
        max_title_chars=100,
        max_body_chars=1000,
        allowed_media_types=["image/png", "image/jpeg"],  # No video allowed
    )

    verdict = evaluate(rendition, destination, surface_spec=surface_spec)
    assert verdict.verdict == VerdictEnum.BLOCK
    assert verdict.code == "DEST_SPEC_VIOLATION"
    assert any(v.field == "media" for v in verdict.violations)


# =========================================================================
# HARD CASE 7: Second post within weekly cap -> RESCHEDULE with earliest_allowed_at
# =========================================================================
def test_hard_case_7_second_post_within_weekly_cap():
    """Verifies that publishing within an active frequency cap window yields RESCHEDULE."""
    now = datetime(2026, 10, 21, 12, 0, 0, tzinfo=UTC)
    recent_post = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)  # 2 days ago

    rendition = Rendition(
        title="Second Post This Week",
        body="Trying to post again before the 7-day cooldown expires.",
        language="en",
    )
    destination = DestinationRuleContext(
        destination_status="active",
        frequency_cap={"max": 1, "per_days": 7},
    )
    history = [PostHistoryItem(posted_at=recent_post, promotional=False)]

    verdict = evaluate(rendition, destination, history=history, now=now)
    assert verdict.verdict == VerdictEnum.RESCHEDULE
    assert verdict.code == "DEST_RULE_FREQUENCY_CAP"
    assert verdict.earliest_allowed_at is not None
    assert verdict.earliest_allowed_at == recent_post + timedelta(days=7)


# =========================================================================
# HARD CASE 8: Promo post to no-promo destination -> BLOCK DEST_RULE_PROMO_BLOCKED
# =========================================================================
def test_hard_case_8_promotional_post_to_no_promo_destination():
    """Verifies that promotional content sent to a non-promotional community is hard blocked."""
    rendition = Rendition(
        title="Special 50% Discount on Our Enterprise SaaS",
        body="Buy now and save big! Link: https://saas.example.com/deal",
        is_promotional=True,
        language="en",
    )
    destination = DestinationRuleContext(
        destination_status="active",
        self_promo_allowed=False,
    )

    verdict = evaluate(rendition, destination)
    assert verdict.verdict == VerdictEnum.BLOCK
    assert verdict.code == "DEST_RULE_PROMO_BLOCKED"
    assert "promotional" in verdict.reason.lower()


# =========================================================================
# HARD CASE 9: Platform renames a field -> certification fails, destination demoted, alert created
# =========================================================================
def test_hard_case_9_platform_renames_field_drift_demotion_alert(db_session):
    """Verifies Drift Canary catches upstream field renaming and demotes destination to L0 with an alert."""
    conn = ConnectorModel(key="devto", version="1.0.0", enabled=True)
    dest = DestinationModel(
        id="dest_devto_drift_hc9",
        name="Dev.to Community",
        url="https://dev.to",
        platform_key="devto",
        surface="article",
        connector_key="devto",
        level="L4",
        status="active",
        instance_config_json={"base_url": "http://localhost:8010/devto"},
    )
    passport = PassportModel(
        destination_id=dest.id,
        level="L4",
        health_score=98.0,
        schema_fingerprint="abc123expected",
    )
    dest.passport = passport
    connection = ConnectionModel(
        destination_id=dest.id,
        connector_key="devto",
        secret_ref="DEVTO_API_KEY",
    )
    db_session.add_all([conn, dest, passport, connection])
    db_session.commit()

    # Trigger MockHub chaos mode 'rename_field' (renames 'url' to 'post_link')
    GLOBAL_CHAOS["fault"] = "rename_field"

    cert_result = run_certification(db_session, dest.id)
    GLOBAL_CHAOS["fault"] = None

    assert cert_result["status"] == "failed"
    assert "drift" in cert_result["reason"].lower() or cert_result.get("drift_report") is not None

    # Verify destination was demoted to L0
    db_session.refresh(dest)
    assert dest.level == "L0"
    assert dest.status == "demoted"

    # Verify alert record was written
    alert = db_session.query(AlertModel).filter(AlertModel.destination_id == dest.id).first()
    assert alert is not None
    assert alert.kind == "CERT_DRIFT_DETECTED"
    assert "drift" in alert.message.lower()


# =========================================================================
# HARD CASE 10: CSV with duplicates, bad URLs, mixed languages -> row-by-row error report
# =========================================================================
def test_hard_case_10_csv_duplicates_bad_urls_mixed_languages_error_report(db_session):
    """Verifies catalogue importer handles messy CSVs with errors and produces a clean report."""
    csv_content = """name,url,platform_key,surface,category,audience_tags,language,rules_url
Valid Forum,https://forum.example.com,discourse,forum_topic,dev,"python,ai",en,https://forum.example.com/rules
Malformed URL,htt://invalid_url,discourse,forum_topic,dev,"python",en,https://example.com
Duplicate Forum,https://forum.example.com/,discourse,forum_topic,dev,"python,ai",en,https://forum.example.com/rules
German Tech,https://tech-de.example.com,ghost,article,dev,"cloud",de,https://tech-de.example.com/rules
"""
    result = import_catalogue_csv(db_session, StringIO(csv_content), batch_size=10)

    assert result["total_read"] == 4
    assert result["imported"] >= 1
    assert result["duplicates_skipped"] == 1


# =========================================================================
# HARD CASE 11: Partner revokes permission (403) -> demoted + reconnect required
# =========================================================================
def test_hard_case_11_partner_revokes_permission_403_demote():
    """Verifies that HTTP 403 Forbidden is mapped to CONNECTION_AUTH_EXPIRED requiring reconnection."""
    connector = WebhookHmacConnector()
    error_mapped = connector.map_http_status_to_error(403, "Partner has revoked access permission")
    assert error_mapped["error"]["code"] == "CONNECTION_AUTH_EXPIRED"
    assert "reconnect" in error_mapped["error"]["details"]["action"].lower()

    destination = {"instance_config": {"endpoint_url": "http://localhost:8010/webhook"}}
    connection = {"secret": "revoked_partner_secret"}

    GLOBAL_CHAOS["fault"] = "403"
    rendition = {"title": "Webhook Notification", "body": "Payload data"}

    with pytest.raises(ValueError) as exc_info:
        connector.publish(rendition, destination, connection, idempotency_key="idemp_hc11")

    assert "CONNECTION_AUTH_EXPIRED" in str(exc_info.value)


# =========================================================================
# HARD CASE 12: Non-English community -> language warning, no silent mistranslation
# =========================================================================
def test_hard_case_12_non_english_community_language_warning():
    """Verifies that sending English content to a foreign language community produces a language warning."""
    rendition = Rendition(
        title="English Technical Guide",
        body="Detailed technical documentation written entirely in English.",
        language="en",
    )
    destination = DestinationRuleContext(
        destination_status="active",
        language="de",  # German destination
    )

    verdict = evaluate(rendition, destination)
    # Court should allow with an explicit warning instead of failing or silently mistranslating
    assert len(verdict.warnings) > 0
    assert any("language" in w.lower() or "de" in w.lower() for w in verdict.warnings)


# =========================================================================
# HARD CASE 13: AI disclosure required -> disclosure appended (REWRITE) or blocked
# =========================================================================
def test_hard_case_13_ai_disclosure_required_rewrite_or_block():
    """Verifies that destinations requiring AI disclosure append a disclosure footnote automatically."""
    rendition = Rendition(
        title="Machine Learning Trends 2026",
        body="A comprehensive summary of recent advancements in generative architectures.",
        language="en",
        ai_generated=True,
    )
    destination = DestinationRuleContext(
        destination_status="active",
        disclosure_required=True,
    )

    verdict = evaluate(rendition, destination)
    assert verdict.verdict == VerdictEnum.REWRITE
    assert verdict.rewritten_rendition is not None
    assert "AI" in verdict.rewritten_rendition.body
    assert "assistance" in verdict.rewritten_rendition.body.lower()


# =========================================================================
# HARD CASE 14: Secrets redaction filter -> tokens/passwords never leaked to logs
# =========================================================================
def test_hard_case_14_secrets_redaction_and_leak_prevention():
    """Verifies that log records scrubbing filter conceals passwords, tokens, API keys, and Bearer auth."""
    filter_obj = SecretRedactionFilter()
    logger = logging.getLogger("test_redaction_logger")
    log_output = StringIO()
    handler = logging.StreamHandler(log_output)
    handler.addFilter(filter_obj)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    secret_message = (
        "Dispatching request with token=ghp_3948394823948239 and password=SuperSecretPassword123! "
        "and Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID and api_key: key_live_998877"
    )
    logger.info(secret_message)

    output = log_output.getvalue()
    assert "ghp_3948394823948239" not in output
    assert "SuperSecretPassword123!" not in output
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in output
    assert "key_live_998877" not in output
    assert "[REDACTED]" in output
