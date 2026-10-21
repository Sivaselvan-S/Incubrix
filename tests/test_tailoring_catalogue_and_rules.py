"""Tests for Content Tailoring, Catalogue Streaming Import with Deduplication, and Rules Capture."""

import time
from pathlib import Path

from app.catalogue.importer import import_catalogue_csv, normalize_destination_url
from app.db.models import AuditLogModel, DestinationModel
from app.rules_capture.extractor import extract_rules_from_text
from app.tailor.engine import tailor_content, truncate_word_boundary


# ------------------------------------------------------------------------------
# Content Tailoring Engine Tests
# ------------------------------------------------------------------------------
def test_tailor_forum_surface():
    """Asserts forum surface rewrites title to discussion hook and appends discussion prompt."""
    rendition = {
        "title": "Decentralized Architecture in 2026",
        "body": "Here is an in-depth breakdown of p2p protocols.",
    }
    destination = {"surface": "forum", "platform_key": "discourse"}

    out = tailor_content(rendition, destination)
    assert out.title.endswith("— What are your thoughts?")
    assert "What are your thoughts on this? Join the discussion below." in out.body
    assert "forum_discussion_title_hook" in out.modifications


def test_tailor_chat_surface():
    """Asserts chat surface formats lengthy text into bullet points."""
    rendition = {
        "title": "Deployment Summary",
        "body": "Container deployment completed in 12 seconds. All integration tests passed with zero errors. System is now handling traffic at 10k req/s.",
    }
    destination = {"surface": "chat", "platform_key": "slack"}

    out = tailor_content(rendition, destination)
    assert "Key Highlights:" in out.body
    assert "• Container deployment completed in 12 seconds." in out.body
    assert "chat_bullet_summary_formatted" in out.modifications


def test_tailor_ai_disclosure_and_link_stripping():
    """Asserts AI disclosure is enforced and URL shorteners are stripped when required."""
    rendition = {
        "title": "AI Powered Code Generation",
        "body": "Check out our new framework at https://bit.ly/super-tool! It generates tests.",
        "ai_generated": True,
    }
    destination = {
        "surface": "article",
        "platform_key": "devto",
        "disclosure_required": True,
        "self_promo_allowed": False,
        "link_policy": "no_shorteners",
    }

    out = tailor_content(rendition, destination)
    assert "Note: This content was generated with assistance from AI." in out.body
    assert "https://bit.ly" not in out.body
    assert "[link removed]" in out.body
    assert "ai_disclosure_appended" in out.modifications
    assert "disallowed_shorteners_removed" in out.modifications


def test_truncate_word_boundary():
    """Asserts word boundary truncation does not split words in half."""
    text = "The quick brown fox jumps over the lazy dog"
    truncated = truncate_word_boundary(text, 20)
    assert len(truncated) <= 20
    assert truncated.endswith("...")
    assert not truncated.endswith("th...")  # Not cut mid-word


# ------------------------------------------------------------------------------
# URL Normalization & Deduplication Tests
# ------------------------------------------------------------------------------
def test_normalize_destination_url():
    """Asserts URL normalization strips www, trailing slashes, and marketing tracking query params."""
    raw = "HTTPS://WWW.Example.com/forum/tech/?utm_source=twitter&utm_medium=social&ref=share#top"
    normalized = normalize_destination_url(raw)
    assert normalized == "https://example.com/forum/tech"

    raw2 = "http://dev.to/user/post/"
    assert normalize_destination_url(raw2) == "http://dev.to/user/post"


def test_catalogue_import_deduplication(db_session):
    """Asserts catalogue import deduplicates identical normalized URLs."""
    csv_data = """name,url,platform_key,surface,category,language,frequency_cap_days,self_promo_allowed,disclosure_required
Forum 1,https://example.org/forum,discourse,forum,tech,en,7,true,false
Forum 1 Duplicate,https://www.example.org/forum/?utm_source=test,discourse,forum,tech,en,7,true,false
Forum 2 Unique,https://another-domain.org/community,lemmy,community,tech,en,3,true,true
"""
    result = import_catalogue_csv(db_session, csv_data, batch_size=10)
    assert result["total_read"] == 3
    assert result["imported"] == 2
    assert result["duplicates_skipped"] == 1


# ------------------------------------------------------------------------------
# 1,000-Row Catalogue Import Benchmark
# ------------------------------------------------------------------------------
def test_1000_row_catalogue_benchmark(db_session):
    """Benchmarks streaming import of 1,000 destinations; must complete in < 5 minutes (< 300s)."""
    csv_path = Path("data") / "destinations_1000.csv"
    assert csv_path.exists(), "Benchmark CSV data/destinations_1000.csv must exist."

    start_time = time.perf_counter()
    summary = import_catalogue_csv(db_session, csv_path, batch_size=250)
    elapsed_time = time.perf_counter() - start_time

    assert summary["total_read"] == 1000
    assert summary["imported"] >= 900
    assert summary["duplicates_skipped"] >= 40
    # Must be under 5 minutes (300s); in local Python/SQLite it finishes in < 2 seconds
    assert elapsed_time < 300.0, f"Import took {elapsed_time:.2f}s, exceeding 300s limit"


# ------------------------------------------------------------------------------
# Rules Capture & Human Confirmation Tests
# ------------------------------------------------------------------------------
def test_extract_rules_from_text():
    """Asserts rule extractor identifies frequency, promo bans, shortener bans, and AI disclosure."""
    policy = """
    Community Policy:
    1. Maximum 1 post per week on Sundays.
    2. Zero promo or affiliate advertising allowed.
    3. No URL shorteners like bit.ly.
    4. AI disclosure required for all generated submissions.
    """
    res = extract_rules_from_text(policy)
    rules = res["rules"]

    assert rules["frequency_cap"] == {"max": 1, "per_days": 7}
    assert rules["self_promo_allowed"] is False
    assert rules["link_policy"] == "no_shorteners"
    assert rules["disclosure_required"] is True
    assert res["confidence"] >= 0.85


def test_rules_api_extract_and_confirm(client, db_session):
    """Asserts POST /api/v1/rules/extract and POST /api/v1/rules/confirm with audit logging."""
    # 1. Setup destination in DB
    dest = DestinationModel(
        id="dest_rule_test_01",
        name="Strict Dev Forum",
        url="https://strict.dev/forum",
        platform_key="discourse",
        connector_key="discourse",
        surface="forum",
        status="active",
        self_promo_allowed=True,
    )
    db_session.add(dest)
    db_session.commit()

    # 2. Extract rules via API
    extract_resp = client.post(
        "/api/v1/rules/extract",
        json={"text": "No self-promotion allowed. All AI content must be labeled. Max 1 post every 30 days."},
    )
    assert extract_resp.status_code == 200
    extracted = extract_resp.json()
    assert extracted["rules"]["self_promo_allowed"] is False
    assert extracted["rules"]["frequency_cap"]["per_days"] == 30

    # 3. Confirm rules via API
    confirm_resp = client.post(
        "/api/v1/rules/confirm",
        json={
            "destination_id": dest.id,
            "confirmed_rules": extracted["rules"],
            "actor": "compliance_officer_bob",
        },
    )
    assert confirm_resp.status_code == 200
    data = confirm_resp.json()
    assert data["status"] == "confirmed"
    assert data["rules_confirmed_by"] == "compliance_officer_bob"

    # 4. Verify DB destination was updated
    db_session.refresh(dest)
    assert dest.self_promo_allowed is False
    assert dest.rules_confirmed_by == "compliance_officer_bob"
    assert dest.rules_confirmed_at is not None

    # 5. Verify immutable Audit Log entry was recorded
    audit = db_session.query(AuditLogModel).filter(AuditLogModel.entity_id == dest.id).first()
    assert audit is not None
    assert audit.action == "RULES_CONFIRMED"
    assert audit.actor == "compliance_officer_bob"
    assert audit.diff_json["after"]["self_promo_allowed"] is False


def test_catalogue_api_import_csv(client):
    """Asserts POST /api/v1/destinations/import-csv endpoint ingests CSV text."""
    csv_payload = {
        "csv_content": """name,url,platform_key,surface,category,language,frequency_cap_days,self_promo_allowed,disclosure_required
API Imported Destination,https://api-imported.org/blog,ghost,article,tech,en,7,true,false
"""
    }
    resp = client.post("/api/v1/destinations/import-csv", json=csv_payload)
    assert resp.status_code == 201
    res_data = resp.json()
    assert res_data["status"] == "completed"
    assert res_data["summary"]["imported"] == 1
