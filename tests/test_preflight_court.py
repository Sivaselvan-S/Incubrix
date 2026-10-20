"""Table-driven test suite for pure-function Preflight Court rules engine."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from app.rules.court import evaluate
from app.rules.schemas import (
    DestinationRuleContext,
    PostHistoryItem,
    Rendition,
    SurfaceSpec,
)

CASES_FILE = Path(__file__).parent / "rules_cases.yaml"
with open(CASES_FILE, encoding="utf-8") as f:
    raw_data = yaml.safe_load(f)
TEST_CASES = raw_data.get("cases", [])


@pytest.mark.parametrize("case", TEST_CASES, ids=[c["id"] for c in TEST_CASES])
def test_preflight_court_case(case: dict):
    """Executes a single test scenario from tests/rules_cases.yaml against Preflight Court."""
    now = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)

    # 1. Build Rendition
    rend_data = case.get("rendition", {})
    rendition = Rendition(**rend_data)

    # 2. Build DestinationRuleContext
    dest_data = case.get("destination", {})
    destination = DestinationRuleContext(**dest_data)

    # 3. Build SurfaceSpec
    spec_data = case.get("surface_spec", {})
    surface_spec = SurfaceSpec(**spec_data)

    # 4. Build PostHistory
    history: list[PostHistoryItem] = []
    days_ago_list = case.get("history_days_ago", [])
    for d in days_ago_list:
        posted_at = now - timedelta(days=d)
        history.append(PostHistoryItem(posted_at=posted_at))

    # 5. Evaluate
    verdict = evaluate(
        rendition=rendition,
        destination=destination,
        history=history,
        surface_spec=surface_spec,
        now=now,
    )

    # 6. Verify verdict
    assert verdict.verdict.value == case["expected_verdict"], (
        f"[{case['id']}] Expected verdict {case['expected_verdict']}, got {verdict.verdict.value}. Reason: {verdict.reason}"
    )

    # 7. Verify error code if expected
    if "expected_code" in case:
        assert verdict.code == case["expected_code"], (
            f"[{case['id']}] Expected code {case['expected_code']}, got {verdict.code}"
        )

    # 8. Verify warning substring if expected
    if "expected_warning_substr" in case:
        expected_substr = case["expected_warning_substr"]
        assert any(expected_substr in w for w in verdict.warnings), (
            f"[{case['id']}] Expected warning containing '{expected_substr}', got warnings: {verdict.warnings}"
        )

    # 9. Verify specific invariant conditions
    if case["expected_verdict"] == "RESCHEDULE":
        assert verdict.earliest_allowed_at is not None
        assert verdict.earliest_allowed_at > now

    if case["expected_verdict"] == "REWRITE":
        assert verdict.rewritten_rendition is not None
        if surface_spec.max_title_chars:
            assert len(verdict.rewritten_rendition.title) <= surface_spec.max_title_chars
        if surface_spec.max_body_chars:
            assert len(verdict.rewritten_rendition.body) <= surface_spec.max_body_chars


def test_preflight_api_endpoint(client, db_session):
    """Asserts POST /api/v1/preflight endpoint functions correctly via HTTP."""
    from app.db.models import ConnectorModel, DestinationModel

    connector = ConnectorModel(key="discourse_conn", enabled=True)
    db_session.add(connector)
    dest = DestinationModel(
        id="dest-preflight-001",
        name="API Test Dest",
        url="https://forum.example.com",
        platform_key="discourse",
        connector_key="discourse_conn",
        self_promo_allowed=False,
    )
    db_session.add(dest)
    db_session.commit()

    # 1. Test clean post -> ALLOW
    res = client.post(
        "/api/v1/preflight",
        json={
            "destination_id": "dest-preflight-001",
            "rendition": {
                "title": "Valid Tech Article",
                "body": "Explaining algorithms",
                "is_promotional": False,
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "ALLOW"

    # 2. Test promotional post when prohibited -> BLOCK
    res_promo = client.post(
        "/api/v1/preflight",
        json={
            "destination_id": "dest-preflight-001",
            "rendition": {"title": "Buy now", "body": "Discount code", "is_promotional": True},
        },
    )
    assert res_promo.status_code == 200
    data_promo = res_promo.json()
    assert data_promo["verdict"] == "BLOCK"
    assert data_promo["code"] == "DEST_RULE_PROMO_BLOCKED"

    # 3. Test non-existent destination -> 404
    res_404 = client.post(
        "/api/v1/preflight",
        json={
            "destination_id": "non-existent-id",
            "rendition": {"title": "Hello", "body": "World"},
        },
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "DESTINATION_NOT_FOUND"
