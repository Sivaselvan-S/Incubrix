"""Tests for Drift Canary: schema pinning, fingerprinting, drift detection, and auto-demotion."""

from sqlalchemy.orm import Session

from app.certify.drift import calculate_schema_fingerprint, validate_response_schema
from app.db.models import AlertModel, ConnectorModel, DestinationModel, PassportModel
from app.passport.engine import demote_destination
from app.rules.court import evaluate
from app.rules.schemas import DestinationRuleContext, Rendition, VerdictEnum


def test_calculate_schema_fingerprint_determinism():
    """Asserts schema fingerprint produces identical hashes for identical structures regardless of key order."""
    data_a = {"id": 123, "title": "Hello", "tags": ["a", "b"], "published": True}
    data_b = {"published": True, "tags": ["b", "a"], "title": "World", "id": 456}

    # Same keys and types produce same fingerprint
    fp_a = calculate_schema_fingerprint(data_a)
    fp_b = calculate_schema_fingerprint(data_b)
    assert fp_a == fp_b

    # Renaming field changes fingerprint
    data_renamed = {"identifier": 123, "title": "Hello", "tags": ["a", "b"], "published": True}
    fp_renamed = calculate_schema_fingerprint(data_renamed)
    assert fp_a != fp_renamed

    # Changing field type (int -> string) changes fingerprint
    data_type_diff = {"id": "123", "title": "Hello", "tags": ["a", "b"], "published": True}
    fp_type = calculate_schema_fingerprint(data_type_diff)
    assert fp_a != fp_type


def test_validate_response_schema_valid():
    """Asserts valid platform response conforms to pinned schema."""
    valid_devto_response = {
        "id": 1005,
        "url": "https://dev.to/article/1005",
        "published": True,
    }
    is_valid, fp, report = validate_response_schema("devto", "publish", valid_devto_response)
    assert is_valid is True
    assert fp is not None
    assert report is None


def test_validate_response_schema_drift_detected():
    """Asserts field rename triggers CERT_DRIFT_DETECTED."""
    # Renamed field: 'url' was renamed to 'live_link' by upstream platform
    drifted_response = {
        "id": 1005,
        "live_link": "https://dev.to/article/1005",
        "published": True,
    }
    is_valid, fp, report = validate_response_schema("devto", "publish", drifted_response)
    assert is_valid is False
    assert report is not None
    assert report["code"] == "CERT_DRIFT_DETECTED"
    assert any("'url' is a required property" in msg for msg in report["missing_fields"])


def test_drift_auto_demotion_and_preflight_court_block(db_session: Session):
    """Asserts platform drift causes auto-demotion to L0, creates Alert, and blocks in Preflight Court."""
    # 1. Setup certified destination
    conn = ConnectorModel(key="devto", enabled=True)
    db_session.add(conn)
    dest = DestinationModel(
        id="dest_drift_test_01",
        name="Devto Target",
        url="https://dev.to",
        platform_key="devto",
        connector_key="devto",
        level="L4",
        status="active",
    )
    db_session.add(dest)
    passport = PassportModel(
        destination_id=dest.id,
        level="L4",
        health_score=100.0,
    )
    db_session.add(passport)
    db_session.commit()

    # 2. Trigger auto-demotion due to drift
    reason = "Drift Canary detected field mismatch in devto.publish: missing 'url'"
    demoted_dest, alert = demote_destination(
        db_session,
        destination_id=dest.id,
        reason=reason,
        error_code="CERT_DRIFT_DETECTED",
    )
    db_session.commit()

    # Verify destination and passport state
    assert demoted_dest.level == "L0"
    assert demoted_dest.status == "demoted"
    assert passport.level == "L0"
    assert passport.health_score <= 50.0
    assert passport.demotion_reason == reason

    # Verify alert row was written
    queried_alert = (
        db_session.query(AlertModel).filter(AlertModel.destination_id == dest.id).first()
    )
    assert queried_alert is not None
    assert queried_alert.kind == "CERT_DRIFT_DETECTED"
    assert queried_alert.resolved is False

    # 3. Assert Preflight Court BLOCKS any post to this demoted destination
    rule_ctx = DestinationRuleContext(
        destination_status=demoted_dest.status,
        connector_enabled=True,
    )
    verdict = evaluate(
        rendition=Rendition(title="Test", body="Valid content"),
        destination=rule_ctx,
    )
    assert verdict.verdict == VerdictEnum.BLOCK
    assert verdict.code == "DESTINATION_DEMOTED"
    assert "not in active state" in verdict.reason
