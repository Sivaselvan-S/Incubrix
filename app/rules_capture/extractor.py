"""Deterministic rule extractor parsing free-form policy text into Preflight Court rules."""

import re
from typing import Any


def extract_rules_from_text(text: str) -> dict[str, Any]:
    """Parses policy guidelines, terms of service, or community rules into structured constraints."""
    lower = text.lower()

    # 1. Frequency Cap extraction
    freq_cap = {"max": 1, "per_days": 7}  # default
    if "once a day" in lower or "1 per day" in lower or "daily" in lower:
        freq_cap = {"max": 1, "per_days": 1}
    elif "twice a week" in lower or "2 per week" in lower:
        freq_cap = {"max": 2, "per_days": 7}
    elif "once a week" in lower or "1 per week" in lower or "weekly" in lower:
        freq_cap = {"max": 1, "per_days": 7}
    elif "once a month" in lower or "monthly" in lower or "every 30 days" in lower:
        freq_cap = {"max": 1, "per_days": 30}
    else:
        # Regex search for: max N posts per D days
        m = re.search(r"(\d+)\s*posts?\s*(?:per|every)\s*(\d+)\s*days?", lower)
        if m:
            freq_cap = {"max": int(m.group(1)), "per_days": int(m.group(2))}

    # 2. Self-promotion allowed
    self_promo = True
    if any(
        phrase in lower
        for phrase in (
            "no self-promotion",
            "no promo",
            "self-promo is forbidden",
            "no advertising",
            "zero promo",
            "no self promotion",
            "commercial posts are banned",
        )
    ):
        self_promo = False

    # 3. Link policy
    link_policy = "none"
    if any(
        phrase in lower
        for phrase in ("no shorteners", "no url shorteners", "no bitly", "no shortened links")
    ):
        link_policy = "no_shorteners"
    elif any(
        phrase in lower
        for phrase in ("no links", "links forbidden", "text only", "no external links")
    ):
        link_policy = "none"
    elif "allowlist only" in lower or "trusted domains only" in lower:
        link_policy = "allowlist"

    # 4. AI Disclosure required
    disclosure_required = False
    if any(
        phrase in lower
        for phrase in (
            "ai disclosure required",
            "must disclose ai",
            "ai content must be labeled",
            "ai-generated content must state",
            "disclose use of generative ai",
            "label ai assistance",
        )
    ):
        disclosure_required = True

    # 5. Automation allowed
    automation_allowed = True
    if any(
        phrase in lower
        for phrase in (
            "no bots",
            "no automated posting",
            "manual submission only",
            "human posts only",
            "api posting disabled",
        )
    ):
        automation_allowed = False

    # Confidence calculation based on matched signals
    signals_matched = sum(
        [
            freq_cap != {"max": 1, "per_days": 7},
            not self_promo,
            link_policy != "none",
            disclosure_required,
            not automation_allowed,
        ]
    )
    confidence = min(0.98, 0.75 + (signals_matched * 0.05))

    return {
        "rules": {
            "frequency_cap": freq_cap,
            "self_promo_allowed": self_promo,
            "link_policy": link_policy,
            "disclosure_required": disclosure_required,
            "automation_allowed": automation_allowed,
        },
        "confidence": round(confidence, 2),
        "source_summary": f"Extracted {signals_matched} rule constraints from {len(text)} chars.",
    }
