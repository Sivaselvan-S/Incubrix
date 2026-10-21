"""Content Tailoring Engine applying surface-specific transformations and rule adaptations."""

import re
from typing import Any

from app.tailor.schemas import TailorOutput

SHORTENER_PATTERN = re.compile(
    r"https?://(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|is\.gd|buff\.ly)/[a-zA-Z0-9_\-]+",
    re.IGNORECASE,
)

AI_DISCLOSURE_FOOTER = "\n\n*Note: This content was generated with assistance from AI.*"
FORUM_PROMPT = "\n\n---\n*What are your thoughts on this? Join the discussion below.*"


def truncate_word_boundary(text: str, max_chars: int) -> str:
    """Truncates text at a clean word boundary with ellipsis."""
    if len(text) <= max_chars:
        return text
    target_len = max_chars - 3
    sliced = text[:target_len]
    if " " in sliced:
        sliced = sliced.rsplit(" ", 1)[0]
    return sliced + "..."


def extract_tags(text: str) -> list[str]:
    """Extracts hashtag keywords from text body and title."""
    found = re.findall(r"#([a-zA-Z0-9_]{2,30})", text)
    tags = list(dict.fromkeys(found))
    if not tags:
        # Default categorical fallbacks
        lower = text.lower()
        if "python" in lower or "fastapi" in lower:
            tags.append("python")
        if "api" in lower or "microservice" in lower:
            tags.append("backend")
        if "docker" in lower or "cloud" in lower:
            tags.append("devops")
    return tags[:5]


def tailor_content(
    rendition: dict[str, Any],
    destination: dict[str, Any],
    surface_spec: dict[str, Any] | None = None,
) -> TailorOutput:
    """Transforms a generic rendition into a destination-tailored publication package.

    1. Discussion-first titles and hooks for forums.
    2. Canonical URL and hashtag extraction for article blogs.
    3. Concise bulletization for chat surfaces.
    4. AI disclosure footers when required by destination rules.
    5. Stripping disallowed shortener links.
    6. Clean word-boundary length compliance.
    """
    spec = surface_spec or {}
    surface = destination.get("surface") or destination.get("platform_key") or "community"
    title = str(rendition.get("title", "Untitled"))
    body = str(rendition.get("body", ""))
    canonical_url = rendition.get("canonical_url")
    ai_generated = bool(rendition.get("ai_generated", False))
    modifications: list[str] = []

    # 1. Surface: Forum / Community (Discourse, Lemmy)
    if surface in ("forum", "community", "discourse", "lemmy"):
        # Discussion-first title if no question mark
        if not title.endswith("?") and not title.lower().startswith(
            ("what", "how", "why", "thoughts on", "discussion:", "ask:")
        ):
            title = f"{title} — What are your thoughts?"
            modifications.append("forum_discussion_title_hook")

        if FORUM_PROMPT.strip() not in body and not body.endswith("?"):
            body += FORUM_PROMPT
            modifications.append("forum_discussion_prompt_appended")

    # 2. Surface: Article / Blog (Dev.to, Ghost, Hashnode)
    elif surface in ("article", "blog", "devto", "ghost", "hashnode"):
        if not canonical_url and rendition.get("url"):
            canonical_url = rendition["url"]
            modifications.append("canonical_url_preserved")

    # 3. Surface: Chat (Slack)
    elif surface in ("chat", "slack", "channel"):
        if len(body) > 100 and "\n• " not in body:
            sentences = [s.strip() for s in body.split(".") if len(s.strip()) > 10]
            if len(sentences) >= 2:
                bullets = "\n".join(f"• {s}." for s in sentences[:3])
                body = f"{title}\n\nKey Highlights:\n{bullets}"
                modifications.append("chat_bullet_summary_formatted")

    # 4. Universal: AI Disclosure Enforcement
    disclosure_required = destination.get("disclosure_required", False)
    if ai_generated and disclosure_required:
        if "generated with assistance from ai" not in body.lower():
            body += AI_DISCLOSURE_FOOTER
            modifications.append("ai_disclosure_appended")

    # 5. Universal: Link Policy & Self-Promo Stripping
    link_policy = destination.get("link_policy", "none")
    self_promo = destination.get("self_promo_allowed", True)
    if not self_promo or link_policy in ("no_shorteners", "none"):
        if SHORTENER_PATTERN.search(body):
            body = SHORTENER_PATTERN.sub("[link removed]", body)
            modifications.append("disallowed_shorteners_removed")

    # 6. Surface Limits Truncation
    max_title = spec.get("max_title_chars", 255)
    max_body = spec.get("max_body_chars", 50000)

    if len(title) > max_title:
        title = truncate_word_boundary(title, max_title)
        modifications.append("title_truncated_to_limit")

    if len(body) > max_body:
        body = truncate_word_boundary(body, max_body)
        modifications.append("body_truncated_to_limit")

    tags = rendition.get("tags") or extract_tags(f"{title} {body}")
    media_urls = rendition.get("media_urls") or ([rendition["media_url"]] if rendition.get("media_url") else [])

    return TailorOutput(
        title=title,
        body=body,
        canonical_url=canonical_url,
        tags=tags,
        media_urls=media_urls,
        modifications=modifications,
        ai_generated=ai_generated,
    )
