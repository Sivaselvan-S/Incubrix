from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VerdictEnum(StrEnum):
    """The five possible verdicts rendered by the Preflight Court."""

    ALLOW = "ALLOW"
    REWRITE = "REWRITE"
    RESCHEDULE = "RESCHEDULE"
    BLOCK = "BLOCK"
    ASSIST = "ASSIST"


class FieldViolation(BaseModel):
    """Details a specific constraint violation on a rendition field."""

    field: str
    rule: str
    limit: Any
    actual: Any


class Rendition(BaseModel):
    """Content candidate being evaluated for publication."""

    title: str = ""
    body: str = ""
    links: list[str] = Field(default_factory=list)
    media: list[str] = Field(default_factory=list)  # MIME types or media URLs
    is_promotional: bool = False
    ai_generated: bool = False
    canonical_url: str | None = None
    language: str = "en"

    model_config = ConfigDict(extra="ignore")


class SurfaceSpec(BaseModel):
    """Physical format constraints defined by the connector surface manifest."""

    max_title_chars: int | None = None
    max_body_chars: int | None = None
    allowed_media_types: list[str] | None = None
    links_allowed: bool = True

    model_config = ConfigDict(extra="ignore")


class DestinationRuleContext(BaseModel):
    """Combined rule set, status, and passport health for a destination."""

    connector_enabled: bool = True
    circuit_open: bool = False
    destination_status: str = "active"  # active | demoted | disabled
    passport_expired: bool = False
    automation_allowed: bool = True
    self_promo_allowed: bool = True
    link_policy: str = "none"  # none | max_n | no_shorteners | domain_allowlist
    link_policy_config: dict[str, Any] = Field(default_factory=dict)
    disclosure_required: bool = False
    frequency_cap: dict[str, int] = Field(default_factory=lambda: {"max": 1, "per_days": 7})
    language: str = "en"

    model_config = ConfigDict(extra="ignore")


class PostHistoryItem(BaseModel):
    """Historical post record evaluated against frequency and promo limits."""

    posted_at: datetime
    promotional: bool = False


class CourtVerdict(BaseModel):
    """Deterministic verdict output from Preflight Court."""

    verdict: VerdictEnum
    rule_id: str
    code: str | None = None
    reason: str
    rewritten_rendition: Rendition | None = None
    earliest_allowed_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)
    violations: list[FieldViolation] = Field(default_factory=list)
