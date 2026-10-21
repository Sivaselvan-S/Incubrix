"""Tests for Recommender Engine, Precision@10 Evaluation, Recertification Scheduler, and Metrics Fetcher."""

from datetime import UTC, datetime, timedelta

from app.db.models import DestinationModel, PassportModel, PublicationModel
from app.metrics.service import fetch_and_record_metrics, get_latest_metrics_for_publication
from app.passport.scheduler import scan_and_enqueue_recertifications
from app.recommend.engine import calculate_relevance_score, recommend_destinations
from scripts.eval_recommender import LABELED_SET_FILE, create_eval_db, evaluate_precision_at_k


# ------------------------------------------------------------------------------
# Recommender Scoring & Filtering Tests
# ------------------------------------------------------------------------------
def test_relevance_calculation():
    """Asserts relevance score rewards topic, category, tag overlap, and language."""
    dest = DestinationModel(
        name="Python Backend Forum",
        url="https://python.example.org",
        platform_key="discourse",
        category="python",
        audience_tags=["fastapi", "asyncio", "backend"],
        language="en",
    )

    # 1. Matching content
    rendition_match = {
        "title": "High performance FastAPI async services",
        "body": "Building microservices with Python and asyncio.",
        "category": "python",
        "tags": ["fastapi", "backend"],
        "language": "en",
    }
    score_match = calculate_relevance_score(rendition_match, dest)
    assert score_match >= 0.70

    # 2. Unrelated content
    rendition_unrelated = {
        "title": "Baking Sourdough Bread at Home",
        "body": "Flour and sourdough starter fermentation guide.",
        "category": "cooking",
        "tags": ["food", "recipes"],
        "language": "fr",
    }
    score_unrelated = calculate_relevance_score(rendition_unrelated, dest)
    assert score_unrelated < 0.30


def test_recommender_filters_disallowed_promotional_content(db_session):
    """Asserts destinations that forbid self-promo are filtered out for promo content."""
    # Destination that bans promo
    dest_strict = DestinationModel(
        id="dest_no_promo_01",
        name="Strict Discussion Board",
        url="https://nopromo.org",
        platform_key="discourse",
        connector_key="discourse",
        surface="forum",
        category="technology",
        self_promo_allowed=False,
        status="active",
        level="L4",
    )
    # Destination that allows promo
    dest_open = DestinationModel(
        id="dest_open_promo_02",
        name="Showcase Board",
        url="https://showcase.org",
        platform_key="discourse",
        connector_key="discourse",
        surface="forum",
        category="technology",
        self_promo_allowed=True,
        status="active",
        level="L4",
    )
    db_session.add_all([dest_strict, dest_open])
    db_session.flush()

    p1 = PassportModel(destination_id=dest_strict.id, level="L4", health_score=100.0)
    p2 = PassportModel(destination_id=dest_open.id, level="L4", health_score=100.0)
    db_session.add_all([p1, p2])
    db_session.commit()

    promo_content = {
        "title": "Special 50% discount on cloud hosting",
        "body": "Use coupon code PROMO50 today!",
        "category": "technology",
        "is_promotional": True,
    }

    recs = recommend_destinations(db_session, promo_content, limit=10)
    dest_ids = [r["destination_id"] for r in recs]

    assert "dest_open_promo_02" in dest_ids
    assert "dest_no_promo_01" not in dest_ids  # Filtered out by rules_fit


def test_recommender_precision_at_10():
    """Asserts Recommender achieves Precision@10 >= 0.70 on the ground-truth benchmark set."""
    eval_db = create_eval_db()
    precision = evaluate_precision_at_k(eval_db, LABELED_SET_FILE, k=10)
    assert precision >= 0.70, f"Expected Precision@10 >= 0.70, got {precision:.2%}"


def test_recommendations_api(client, db_session):
    """Asserts POST /api/v1/recommendations returns sorted recommendations with breakdown."""
    dest = DestinationModel(
        id="dest_api_rec_01",
        name="FastAPI Community",
        url="https://fastapi.org",
        platform_key="discourse",
        connector_key="discourse",
        surface="forum",
        category="python",
        status="active",
        level="L3",
    )
    db_session.add(dest)
    db_session.flush()
    db_session.add(PassportModel(destination_id=dest.id, level="L3", health_score=90.0))
    db_session.commit()

    resp = client.post(
        "/api/v1/recommendations",
        json={
            "title": "FastAPI Dependency Injection Tutorial",
            "body": "Learn how FastAPI manages DB sessions and dependencies.",
            "category": "python",
            "tags": ["fastapi", "python"],
            "limit": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    top_rec = data["recommendations"][0]
    assert "destination_id" in top_rec
    assert "final_score" in top_rec
    assert "relevance" in top_rec
    assert "rules_fit" in top_rec


# ------------------------------------------------------------------------------
# Recertification Scheduler Tests
# ------------------------------------------------------------------------------
def test_recertification_scheduler_enqueues_stale_passports(db_session):
    """Asserts recertification scheduler discovers stale Passports and enqueues certify jobs."""
    # 1. Fresh passport (certified 2 days ago)
    dest_fresh = DestinationModel(
        id="dest_fresh_01",
        name="Freshly Certified Destination",
        url="https://fresh.example.org",
        platform_key="discourse",
        connector_key="discourse",
        status="active",
        level="L3",
    )
    # 2. Stale passport (certified 30 days ago)
    dest_stale = DestinationModel(
        id="dest_stale_02",
        name="Stale Destination",
        url="https://stale.example.org",
        platform_key="discourse",
        connector_key="discourse",
        status="active",
        level="L3",
    )
    db_session.add_all([dest_fresh, dest_stale])
    db_session.flush()

    p_fresh = PassportModel(
        destination_id=dest_fresh.id,
        level="L3",
        health_score=90.0,
        last_certified_at=datetime.now(UTC) - timedelta(days=2),
    )
    p_stale = PassportModel(
        destination_id=dest_stale.id,
        level="L3",
        health_score=85.0,
        last_certified_at=datetime.now(UTC) - timedelta(days=30),
    )
    db_session.add_all([p_fresh, p_stale])
    db_session.commit()

    # Run 25-day scheduler scan
    res = scan_and_enqueue_recertifications(db_session, max_age_days=25, demo_mode=False)
    assert res["stale_count"] == 1
    assert len(res["enqueued_job_ids"]) == 1


def test_recertification_api_endpoint(client, db_session):
    """Asserts POST /api/v1/destinations/recertify-stale triggers scheduler on demand."""
    resp = client.post("/api/v1/destinations/recertify-stale", params={"demo_mode": False})
    assert resp.status_code == 200
    data = resp.json()
    assert "stale_count" in data
    assert "enqueued_job_ids" in data


# ------------------------------------------------------------------------------
# Normalized Metrics Fetcher Tests
# ------------------------------------------------------------------------------
def test_fetch_and_record_metrics(db_session):
    """Asserts metrics fetcher queries connector and persists normalized snapshot in metrics table."""
    dest = DestinationModel(
        id="dest_metrics_test_01",
        name="Discourse Metrics Dest",
        url="http://localhost:8010",
        platform_key="discourse",
        connector_key="discourse",
        status="active",
    )
    db_session.add(dest)
    db_session.flush()

    pub = PublicationModel(
        id="pub_metrics_test_01",
        destination_id=dest.id,
        content_id="content_test",
        idempotency_key="metrics_idem_1",
        platform_post_id="42",
        state="SUCCEEDED",
    )
    db_session.add(pub)
    db_session.commit()

    # Trigger metrics fetch
    metrics = fetch_and_record_metrics(db_session, pub.id)
    assert metrics["publication_id"] == pub.id
    assert metrics["platform_post_id"] == "42"
    assert metrics["views"] > 0
    assert metrics["likes"] >= 0

    # Retrieve snapshot
    latest = get_latest_metrics_for_publication(db_session, pub.id)
    assert latest is not None
    assert latest["views"] == metrics["views"]


def test_metrics_api_routes(client, db_session):
    """Asserts POST and GET /api/v1/publications/{id}/metrics endpoints work seamlessly."""
    dest = DestinationModel(
        id="dest_pub_metrics_api",
        name="Devto Blog",
        url="http://localhost:8010",
        platform_key="devto",
        connector_key="devto",
        status="active",
    )
    db_session.add(dest)
    db_session.flush()

    pub = PublicationModel(
        id="pub_api_metrics_01",
        destination_id=dest.id,
        content_id="content_api",
        idempotency_key="api_idem_metrics",
        platform_post_id="101",
        state="SUCCEEDED",
    )
    db_session.add(pub)
    db_session.commit()

    # 1. POST fetch metrics
    post_res = client.post(f"/api/v1/publications/{pub.id}/metrics")
    assert post_res.status_code == 201
    post_data = post_res.json()
    assert post_data["views"] == 210  # Dev.to simulated views
    assert post_data["likes"] == 35

    # 2. GET retrieved metrics
    get_res = client.get(f"/api/v1/publications/{pub.id}/metrics")
    assert get_res.status_code == 200
    assert get_res.json()["views"] == 210
