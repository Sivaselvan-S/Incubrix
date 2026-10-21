"""Metrics aggregation service querying connectors and persisting normalized engagement stats."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.connectors.registry import get_connector
from app.db.models import DestinationModel, MetricsModel, PublicationModel, generate_uuid
from app.logging import get_logger

logger = get_logger("app.metrics.service")


def fetch_and_record_metrics(db: Session, publication_id: str) -> dict[str, Any]:
    """Fetches normalized engagement metrics from the external destination and records in DB."""
    pub = db.query(PublicationModel).filter(PublicationModel.id == publication_id).first()
    if not pub:
        raise ValueError(f"Publication '{publication_id}' not found.")

    if not pub.platform_post_id:
        raise ValueError(f"Publication '{publication_id}' has no platform_post_id to query.")

    dest = db.query(DestinationModel).filter(DestinationModel.id == pub.destination_id).first()
    if not dest:
        raise ValueError(f"Destination '{pub.destination_id}' not found.")

    connector = get_connector(dest.connector_key)
    conn_dict = dest.instance_config_json or {}
    metrics_data = connector.fetch_metrics(pub.platform_post_id, conn_dict)

    record = MetricsModel(
        id=generate_uuid(),
        platform_post_id=pub.platform_post_id,
        publication_id=pub.id,
        destination_id=dest.id,
        views=int(metrics_data.get("views", 0)),
        likes=int(metrics_data.get("likes", 0)),
        comments=int(metrics_data.get("comments", 0)),
        shares=int(metrics_data.get("shares", 0)),
        clicks=int(metrics_data.get("clicks", 0)),
        fetched_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        "Recorded metrics for pub %s: %d views, %d likes, %d comments",
        pub.id,
        record.views,
        record.likes,
        record.comments,
    )

    return {
        "id": record.id,
        "publication_id": pub.id,
        "destination_id": dest.id,
        "platform_post_id": record.platform_post_id,
        "views": record.views,
        "likes": record.likes,
        "comments": record.comments,
        "shares": record.shares,
        "clicks": record.clicks,
        "fetched_at": record.fetched_at.isoformat(),
    }


def get_latest_metrics_for_publication(db: Session, publication_id: str) -> dict[str, Any] | None:
    """Returns the most recent metrics record for a publication."""
    m = (
        db.query(MetricsModel)
        .filter(MetricsModel.publication_id == publication_id)
        .order_by(MetricsModel.fetched_at.desc())
        .first()
    )
    if not m:
        return None
    return {
        "id": m.id,
        "publication_id": m.publication_id,
        "destination_id": m.destination_id,
        "platform_post_id": m.platform_post_id,
        "views": m.views,
        "likes": m.likes,
        "comments": m.comments,
        "shares": m.shares,
        "clicks": m.clicks,
        "fetched_at": m.fetched_at.isoformat(),
    }
