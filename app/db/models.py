"""SQLAlchemy 2 database models for LongTail Passport."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    """Returns current UTC timestamp with timezone."""
    return datetime.now(UTC)


def generate_uuid() -> str:
    """Generates a UUID4 string."""
    return str(uuid.uuid4())


class ConnectorModel(Base):
    """Registered platform connector definition and circuit breaker status."""

    __tablename__ = "connectors"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Kill switch
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    circuit_open_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    destinations: Mapped[list["DestinationModel"]] = relationship(back_populates="connector")


class DestinationModel(Base):
    """A long-tail publishing destination carrying rules, config, and Passport state."""

    __tablename__ = "destinations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    platform_key: Mapped[str] = mapped_column(String(64), nullable=False)
    surface: Mapped[str] = mapped_column(
        String(64), default="community"
    )  # forum | article | chat | bridge
    category: Mapped[str] = mapped_column(String(128), default="general")
    audience_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(16), default="en")
    geo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    est_audience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rules_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Deterministic rules evaluated by Preflight Court
    frequency_cap_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=lambda: {"max": 1, "per_days": 7}
    )
    self_promo_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    link_policy: Mapped[str] = mapped_column(
        String(32), default="none"
    )  # none | max_n | no_shorteners | allowlist
    disclosure_required: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    connector_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("connectors.key"), nullable=False
    )
    instance_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    level: Mapped[str] = mapped_column(String(16), default="L0")  # L0, L1, L2, L3, L4
    last_certified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | demoted | disabled

    rules_confirmed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rules_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    connector: Mapped["ConnectorModel"] = relationship(back_populates="destinations")
    passport: Mapped["PassportModel"] = relationship(back_populates="destination", uselist=False)
    publications: Mapped[list["PublicationModel"]] = relationship(back_populates="destination")

    def to_export_dict(self) -> dict[str, Any]:
        """Exports the exact 20 fields required by the destination record specification."""
        return {
            "name": self.name,
            "url": self.url,
            "platform_key": self.platform_key,
            "surface": self.surface,
            "category": self.category,
            "audience_tags": self.audience_tags,
            "language": self.language,
            "geo": self.geo,
            "est_audience": self.est_audience,
            "rules_url": self.rules_url,
            "frequency_cap": self.frequency_cap_json,
            "self_promo_allowed": self.self_promo_allowed,
            "link_policy": self.link_policy,
            "disclosure_required": self.disclosure_required,
            "automation_allowed": self.automation_allowed,
            "connector_key": self.connector_key,
            "relevance_score": self.relevance_score,
            "relevance_reason": self.relevance_reason,
            "level": self.level,
            "last_certified_at": self.last_certified_at.isoformat()
            if self.last_certified_at
            else None,
        }


class ConnectionModel(Base):
    """References destination secrets by env var or vault key (never raw secrets)."""

    __tablename__ = "connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    connector_key: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("destinations.id"), nullable=False
    )
    secret_ref: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Env var name or key reference
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PassportModel(Base):
    """Living Passport tracking certification, health, schema fingerprint, and level."""

    __tablename__ = "passports"

    destination_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("destinations.id"), primary_key=True
    )
    level: Mapped[str] = mapped_column(String(16), default="L0")  # L0, L1, L2, L3, L4
    health_score: Mapped[float] = mapped_column(Float, default=100.0)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_certified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    demotion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    destination: Mapped["DestinationModel"] = relationship(back_populates="passport")


class PublicationModel(Base):
    """Tracks publication attempts and external platform posts."""

    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    destination_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("destinations.id"), nullable=False
    )
    content_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), default="INTENT"
    )  # INTENT | SUCCEEDED | FAILED | UNKNOWN
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    live_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    destination: Mapped["DestinationModel"] = relationship(back_populates="publications")


class IdempotencyLedgerModel(Base):
    """Guarantees intent-first idempotency and deduplication across all POST operations."""

    __tablename__ = "idempotency_ledger"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), default="INTENT"
    )  # INTENT | SUCCEEDED | FAILED | UNKNOWN
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class JobModel(Base):
    """Postgres-backed background job queue row claimed via SELECT ... FOR UPDATE SKIP LOCKED."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # publication | certify | catalogue_import...
    status: Mapped[str] = mapped_column(
        String(32), default="queued"
    )  # queued | running | succeeded | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0 to 100
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    callback_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CertificationModel(Base):
    """Stores full audit logs, steps, and drift results of connector certification runs."""

    __tablename__ = "certifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    destination_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("destinations.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    drift_report_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class AlertModel(Base):
    """Platform alerts, including circuit-breaking, drift demotions, and expired auth."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    kind: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # CERT_DRIFT_DETECTED | CONNECTOR_DISABLED...
    destination_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class PostHistoryModel(Base):
    """Historical post timestamps used by Preflight Court for frequency cap validation."""

    __tablename__ = "post_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    destination_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("destinations.id"), nullable=False
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    promotional: Mapped[bool] = mapped_column(Boolean, default=False)


class MetricsModel(Base):
    """Normalized metrics scraped or queried from destination platforms."""

    __tablename__ = "metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    platform_post_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
