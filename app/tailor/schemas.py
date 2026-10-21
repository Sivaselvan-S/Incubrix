"""Schemas for Content Tailoring engine."""

from typing import Any

from pydantic import BaseModel, Field


class TailorInput(BaseModel):
    """Input payload for tailoring content to destination surface and rules."""

    rendition: dict[str, Any]
    destination: dict[str, Any]
    surface: str = "community"


class TailorOutput(BaseModel):
    """Tailored output rendition with record of modifications applied."""

    title: str
    body: str
    canonical_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    modifications: list[str] = Field(default_factory=list)
    ai_generated: bool = False
