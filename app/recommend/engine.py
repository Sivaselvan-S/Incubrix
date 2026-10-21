"""Recommender Engine applying multi-criteria scoring to match content with optimal destinations."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DestinationModel, MetricsModel, PostHistoryModel, PublicationModel


def calculate_relevance_score(rendition: dict[str, Any], dest: DestinationModel) -> float:
    """Calculates content-to-destination topical and audience relevance (0.0 to 1.0)."""
    score = 0.0
    text_content = f"{rendition.get('title', '')} {rendition.get('body', '')}".lower()
    rendition_tags = {t.lower() for t in rendition.get("tags", [])}
    rendition_category = str(rendition.get("category", "")).lower()

    # 1. Category alignment (0.35)
    dest_category = (dest.category or "general").lower()
    if dest_category and (dest_category == rendition_category or dest_category in text_content):
        score += 0.35
    elif rendition_category and dest_category in ("general", "all", "tech"):
        score += 0.20

    # 2. Audience tags overlap (0.35)
    dest_tags = {t.lower() for t in (dest.audience_tags or [])}
    if dest_tags and rendition_tags:
        overlap = len(dest_tags.intersection(rendition_tags))
        score += min(0.35, overlap * 0.15)
    elif dest_tags:
        # Check text content for destination tags
        tag_hits = sum(1 for dt in dest_tags if re.search(rf"\b{re.escape(dt)}\b", text_content))
        score += min(0.35, tag_hits * 0.10)
    else:
        score += 0.15

    # 3. Language compatibility (0.20)
    rendition_lang = str(rendition.get("language", "en")).lower()
    dest_lang = (dest.language or "en").lower()
    if dest_lang == rendition_lang:
        score += 0.20

    # 4. Audience size bonus (0.10)
    if dest.est_audience and dest.est_audience > 1000:
        score += min(0.10, dest.est_audience / 50000.0)
    else:
        score += 0.05

    return min(1.0, max(0.0, score))


def calculate_rules_fit_score(
    db: Session,
    rendition: dict[str, Any],
    dest: DestinationModel,
) -> tuple[float, str]:
    """Calculates rules compliance and Preflight Court fit (0.0 to 1.0)."""
    # Hard blocks
    if dest.status != "active":
        return 0.0, "Destination inactive"

    if dest.connector and not dest.connector.enabled:
        return 0.0, "Connector disabled by kill switch"

    if dest.connector and dest.connector.consecutive_failures >= 5:
        return 0.0, "Circuit breaker tripped"

    is_promo = bool(rendition.get("is_promotional", False))
    if is_promo and not dest.self_promo_allowed:
        return 0.0, "Self-promotion disallowed"

    # Passport health and level factor (0.40)
    passport = dest.passport
    passport_level = passport.level if passport else dest.level
    level_weights = {"L4": 0.40, "L3": 0.30, "L2": 0.20, "L1": 0.10, "L0": 0.05}
    health_factor = (passport.health_score / 100.0) if passport else 0.50
    level_score = level_weights.get(passport_level, 0.05) * health_factor

    # Frequency cap readiness (0.35)
    freq_cap = dest.frequency_cap_json or {"max": 1, "per_days": 7}
    per_days = freq_cap.get("per_days", 7)
    cutoff = datetime.now(UTC) - timedelta(days=per_days)

    recent_posts = (
        db.query(PostHistoryModel)
        .filter(PostHistoryModel.destination_id == dest.id, PostHistoryModel.posted_at >= cutoff)
        .count()
    )
    freq_score = 0.35 if recent_posts < freq_cap.get("max", 1) else 0.05

    # Surface format compatibility (0.25)
    format_score = 0.25
    body_len = len(str(rendition.get("body", "")))
    if dest.surface == "chat" and body_len > 4000:
        format_score = 0.10

    total_fit = min(1.0, level_score + freq_score + format_score)
    return total_fit, f"Passport {passport_level} (health {health_factor:.0%}), freq fit: {freq_score:.2f}"


def calculate_past_result_score(db: Session, dest: DestinationModel) -> tuple[float, str]:
    """Calculates historical delivery and engagement reliability (0.0 to 1.0)."""
    pubs = db.query(PublicationModel).filter(PublicationModel.destination_id == dest.id).all()
    if not pubs:
        # Cold start neutral prior
        return 0.50, "Cold start baseline (no prior history)"

    total = len(pubs)
    succeeded = sum(1 for p in pubs if p.state == "SUCCEEDED")
    success_rate = succeeded / total

    # Engagement metric boost
    metrics = (
        db.query(MetricsModel)
        .filter(MetricsModel.destination_id == dest.id)
        .all()
    )
    engagement_boost = 0.0
    if metrics:
        avg_views = sum(m.views for m in metrics) / len(metrics)
        avg_reactions = sum(m.likes + m.comments for m in metrics) / len(metrics)
        engagement_boost = min(0.20, (avg_views / 500.0) * 0.10 + (avg_reactions / 50.0) * 0.10)

    score = min(1.0, (success_rate * 0.80) + engagement_boost)
    return score, f"Delivery success {success_rate:.0%} across {total} posts"


def recommend_destinations(
    db: Session,
    rendition: dict[str, Any],
    limit: int = 10,
    min_score: float = 0.20,
) -> list[dict[str, Any]]:
    """Ranks active destinations using composite formula: 0.50*relevance + 0.25*rules_fit + 0.25*past_result."""
    destinations = db.query(DestinationModel).filter(DestinationModel.status == "active").all()
    candidates: list[dict[str, Any]] = []

    for dest in destinations:
        relevance = calculate_relevance_score(rendition, dest)
        rules_fit, rules_reason = calculate_rules_fit_score(db, rendition, dest)
        if rules_fit <= 0.0:
            # Blocked by destination rules or kill-switch
            continue

        past_score, past_reason = calculate_past_result_score(db, dest)

        # Recommender Scoring Formula
        final_score = round((0.50 * relevance) + (0.25 * rules_fit) + (0.25 * past_score), 4)

        if final_score >= min_score:
            candidates.append({
                "destination_id": dest.id,
                "name": dest.name,
                "url": dest.url,
                "platform_key": dest.platform_key,
                "surface": dest.surface,
                "category": dest.category,
                "passport_level": dest.passport.level if dest.passport else dest.level,
                "final_score": final_score,
                "relevance": round(relevance, 4),
                "rules_fit": round(rules_fit, 4),
                "past_result_score": round(past_score, 4),
                "rationale": f"Relevance {relevance:.0%}, {rules_reason}, {past_reason}",
            })

    # Sort descending by final_score
    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates[:limit]
