"""Pure-function deterministic Preflight Court rules engine."""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from app.rules.schemas import (
    CourtVerdict,
    DestinationRuleContext,
    FieldViolation,
    PostHistoryItem,
    Rendition,
    SurfaceSpec,
    VerdictEnum,
)

# Known URL shortener hostnames blocked by no_shorteners policy
URL_SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "ow.ly",
    "is.gd",
    "buff.ly",
    "rebrand.ly",
    "cutt.ly",
    "goo.gl",
}

AI_DISCLOSURE_TEXT = (
    "\n\n*Transparency Note: This post was prepared with AI assistance and reviewed by a human.*"
)


def truncate_at_word_boundary(text: str, limit: int, ellipsis: str = "...") -> str:
    """Truncates text at a word boundary to fit within limit including ellipsis.

    If limit is smaller than ellipsis or text has no spaces, truncates hard.
    """
    if len(text) <= limit:
        return text

    target_len = limit - len(ellipsis)
    if target_len <= 0:
        return text[:limit]

    # Find the last whitespace before target_len
    truncated = text[: target_len + 1]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space].rstrip() + ellipsis
    return text[:target_len].rstrip() + ellipsis


def evaluate(
    rendition: Rendition,
    destination: DestinationRuleContext,
    history: list[PostHistoryItem] | None = None,
    surface_spec: SurfaceSpec | None = None,
    now: datetime | None = None,
) -> CourtVerdict:
    """Evaluates a rendition against destination rules, surface spec, and post history.

    This function is completely pure and deterministic: zero I/O, zero network, zero state mutation.
    """
    if now is None:
        now = datetime.now(UTC)
    if surface_spec is None:
        surface_spec = SurfaceSpec()
    if history is None:
        history = []

    warnings: list[str] = []

    # --------------------------------------------------------------------------
    # Check 1: Connector status & Circuit breaker
    # --------------------------------------------------------------------------
    if not destination.connector_enabled:
        return CourtVerdict(
            verdict=VerdictEnum.BLOCK,
            rule_id="RULE_CONNECTOR_DISABLED",
            code="CONNECTOR_DISABLED",
            reason="Connector kill switch is active. Publishing is disabled.",
            warnings=warnings,
        )

    if destination.circuit_open:
        return CourtVerdict(
            verdict=VerdictEnum.BLOCK,
            rule_id="RULE_CIRCUIT_OPEN",
            code="PLATFORM_UNAVAILABLE",
            reason="Connector circuit breaker is open due to repeated platform failures.",
            warnings=warnings,
        )

    # --------------------------------------------------------------------------
    # Check 2: Destination status & Passport expiry
    # --------------------------------------------------------------------------
    if destination.destination_status != "active":
        return CourtVerdict(
            verdict=VerdictEnum.BLOCK,
            rule_id="RULE_DESTINATION_NOT_ACTIVE",
            code="DESTINATION_DEMOTED",
            reason=f"Destination is not in active state (status: '{destination.destination_status}').",
            warnings=warnings,
        )

    if destination.passport_expired:
        return CourtVerdict(
            verdict=VerdictEnum.BLOCK,
            rule_id="RULE_PASSPORT_EXPIRED",
            code="DESTINATION_DEMOTED",
            reason="Passport has expired. Destination must be recertified before publishing.",
            warnings=warnings,
        )

    # --------------------------------------------------------------------------
    # Check 3: Automation allowance -> Route to Assisted Pack if false
    # --------------------------------------------------------------------------
    if not destination.automation_allowed:
        return CourtVerdict(
            verdict=VerdictEnum.ASSIST,
            rule_id="RULE_AUTOMATION_PROHIBITED",
            code="ASSISTED_TIER_REQUIRED",
            reason="Destination policy prohibits automated publishing. Routed to assisted workflow pack.",
            warnings=warnings,
        )

    # --------------------------------------------------------------------------
    # Check 4: Physical format limits (surface specification)
    # --------------------------------------------------------------------------
    rewritten = rendition.model_copy(deep=True)
    has_rewrites = False
    violations: list[FieldViolation] = []

    # 4a: Media validation
    if rendition.media and surface_spec.allowed_media_types is not None:
        disallowed_media = [m for m in rendition.media if m not in surface_spec.allowed_media_types]
        if disallowed_media:
            violations.append(
                FieldViolation(
                    field="media",
                    rule="allowed_media_types",
                    limit=surface_spec.allowed_media_types,
                    actual=disallowed_media,
                )
            )

    # 4b: Links allowed check
    if rendition.links and not surface_spec.links_allowed:
        violations.append(
            FieldViolation(
                field="links",
                rule="links_allowed",
                limit=False,
                actual=len(rendition.links),
            )
        )

    if violations:
        return CourtVerdict(
            verdict=VerdictEnum.BLOCK,
            rule_id="RULE_SURFACE_SPEC_VIOLATION",
            code="DEST_SPEC_VIOLATION",
            reason="Rendition violates destination surface specification.",
            violations=violations,
            warnings=warnings,
        )

    # 4c: Title length limit -> Auto-truncate at word boundary if exceeded
    if surface_spec.max_title_chars and len(rewritten.title) > surface_spec.max_title_chars:
        # Check if title can be reasonably truncated
        truncated_title = truncate_at_word_boundary(rewritten.title, surface_spec.max_title_chars)
        if len(truncated_title) > surface_spec.max_title_chars:
            # Extreme boundary where even truncation exceeds limit
            return CourtVerdict(
                verdict=VerdictEnum.BLOCK,
                rule_id="RULE_TITLE_LENGTH",
                code="DEST_SPEC_VIOLATION",
                reason=f"Title cannot be truncated to fit limit of {surface_spec.max_title_chars} characters.",
                violations=[
                    FieldViolation(
                        field="title",
                        rule="max_title_chars",
                        limit=surface_spec.max_title_chars,
                        actual=len(rewritten.title),
                    )
                ],
                warnings=warnings,
            )
        rewritten.title = truncated_title
        has_rewrites = True
        warnings.append(
            f"Title was truncated to {surface_spec.max_title_chars} chars at word boundary."
        )

    # 4d: Body length limit -> Auto-truncate at word boundary if exceeded
    if surface_spec.max_body_chars and len(rewritten.body) > surface_spec.max_body_chars:
        truncated_body = truncate_at_word_boundary(rewritten.body, surface_spec.max_body_chars)
        rewritten.body = truncated_body
        has_rewrites = True
        warnings.append(
            f"Body was truncated to {surface_spec.max_body_chars} chars at word boundary."
        )

    # --------------------------------------------------------------------------
    # Check 5: Self-promotion policy
    # --------------------------------------------------------------------------
    if not destination.self_promo_allowed and rendition.is_promotional:
        return CourtVerdict(
            verdict=VerdictEnum.BLOCK,
            rule_id="RULE_SELF_PROMO_PROHIBITED",
            code="DEST_RULE_PROMO_BLOCKED",
            reason="Self-promotional content is prohibited on this destination. Reframe as an informational discussion.",
            warnings=warnings,
        )

    # --------------------------------------------------------------------------
    # Check 6: Link policy (none | no_shorteners | max_n | domain_allowlist)
    # --------------------------------------------------------------------------
    if destination.link_policy == "no_shorteners" and rendition.links:
        for link in rendition.links:
            host = urlparse(link).netloc.lower()
            if any(host == s or host.endswith("." + s) for s in URL_SHORTENERS):
                return CourtVerdict(
                    verdict=VerdictEnum.BLOCK,
                    rule_id="RULE_LINK_NO_SHORTENERS",
                    code="DEST_RULE_LINK_POLICY",
                    reason=f"URL shorteners are prohibited by destination rules (detected: '{host}').",
                    violations=[
                        FieldViolation(
                            field="links",
                            rule="no_shorteners",
                            limit="direct_urls_only",
                            actual=link,
                        )
                    ],
                    warnings=warnings,
                )

    if destination.link_policy == "max_n":
        max_allowed = destination.link_policy_config.get("max_links", 1)
        if len(rendition.links) > max_allowed:
            return CourtVerdict(
                verdict=VerdictEnum.BLOCK,
                rule_id="RULE_LINK_MAX_N",
                code="DEST_RULE_LINK_POLICY",
                reason=f"Destination permits a maximum of {max_allowed} link(s), but {len(rendition.links)} were provided.",
                violations=[
                    FieldViolation(
                        field="links",
                        rule="max_links",
                        limit=max_allowed,
                        actual=len(rendition.links),
                    )
                ],
                warnings=warnings,
            )

    if destination.link_policy == "domain_allowlist":
        allowed_domains = destination.link_policy_config.get("allowed_domains", [])
        for link in rendition.links:
            host = urlparse(link).netloc.lower()
            if not any(host == d or host.endswith("." + d) for d in allowed_domains):
                return CourtVerdict(
                    verdict=VerdictEnum.BLOCK,
                    rule_id="RULE_LINK_ALLOWLIST",
                    code="DEST_RULE_LINK_POLICY",
                    reason=f"Destination requires links to match allowlist {allowed_domains}; '{host}' is not permitted.",
                    violations=[
                        FieldViolation(
                            field="links",
                            rule="domain_allowlist",
                            limit=allowed_domains,
                            actual=host,
                        )
                    ],
                    warnings=warnings,
                )

    # --------------------------------------------------------------------------
    # Check 7: AI disclosure requirement
    # --------------------------------------------------------------------------
    if destination.disclosure_required and rendition.ai_generated:
        if AI_DISCLOSURE_TEXT.strip() not in rewritten.body:
            potential_len = len(rewritten.body) + len(AI_DISCLOSURE_TEXT)
            max_body = surface_spec.max_body_chars
            if max_body is not None and potential_len > max_body:
                # Body cannot accommodate the mandatory disclosure text
                return CourtVerdict(
                    verdict=VerdictEnum.BLOCK,
                    rule_id="RULE_AI_DISCLOSURE_OVERFLOW",
                    code="DEST_RULE_AI_DISCLOSURE_REQUIRED",
                    reason="AI disclosure is required but appending it exceeds maximum body characters limit.",
                    violations=[
                        FieldViolation(
                            field="body",
                            rule="disclosure_required",
                            limit=max_body,
                            actual=potential_len,
                        )
                    ],
                    warnings=warnings,
                )
            # Append disclosure note
            rewritten.body += AI_DISCLOSURE_TEXT
            has_rewrites = True
            warnings.append("Mandatory AI disclosure was appended to content body.")

    # --------------------------------------------------------------------------
    # Check 8: Frequency cap calculation
    # --------------------------------------------------------------------------
    max_cap = destination.frequency_cap.get("max", 1)
    per_days = destination.frequency_cap.get("per_days", 7)
    window_start = now - timedelta(days=per_days)

    posts_in_window = [p for p in history if p.posted_at >= window_start]
    if len(posts_in_window) >= max_cap:
        # Sort chronologically to find the earliest slot opening
        posts_in_window.sort(key=lambda p: p.posted_at)
        slot_free_after = posts_in_window[0].posted_at + timedelta(days=per_days)
        return CourtVerdict(
            verdict=VerdictEnum.RESCHEDULE,
            rule_id="RULE_FREQUENCY_CAP_EXCEEDED",
            code="DEST_RULE_FREQUENCY_CAP",
            reason=f"Destination frequency cap of {max_cap} post(s) per {per_days} day(s) reached.",
            earliest_allowed_at=slot_free_after,
            warnings=warnings,
        )

    # --------------------------------------------------------------------------
    # Language mismatch advisory warning (never silently mistranslate)
    # --------------------------------------------------------------------------
    if (
        destination.language
        and rendition.language
        and destination.language.lower() != rendition.language.lower()
        and destination.language.lower() != "en"
    ):
        warnings.append(
            f"Destination expects language '{destination.language}' but rendition is '{rendition.language}'."
        )

    # --------------------------------------------------------------------------
    # Final Verdict Resolution: REWRITE vs ALLOW
    # --------------------------------------------------------------------------
    if has_rewrites:
        return CourtVerdict(
            verdict=VerdictEnum.REWRITE,
            rule_id="RULE_AUTO_REWRITE_APPLIED",
            code=None,
            reason="Content was automatically adjusted to meet destination surface limits.",
            rewritten_rendition=rewritten,
            warnings=warnings,
        )

    return CourtVerdict(
        verdict=VerdictEnum.ALLOW,
        rule_id="RULE_ALL_CHECKS_PASSED",
        code=None,
        reason="Content strictly complies with destination rules and specifications.",
        warnings=warnings,
    )
