"""API routes for destination recommendations."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.recommend.engine import recommend_destinations

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommender"])


class RecommendationRequest(BaseModel):
    """Payload for finding matching destinations for a piece of content."""

    title: str = Field(..., description="Post or article title")
    body: str = Field(..., description="Content body")
    category: str = Field("technology", description="Primary topic category")
    tags: list[str] = Field(default_factory=list, description="Content tags")
    language: str = Field("en", description="Content language code")
    is_promotional: bool = Field(False, description="Whether content is promotional")
    limit: int = Field(10, ge=1, le=50, description="Max recommendations to return")


@router.post("")
def get_recommendations(
    payload: RecommendationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Computes destination recommendations ranked by composite multi-criteria scoring."""
    rendition = payload.model_dump()
    recs = recommend_destinations(db, rendition, limit=payload.limit)
    return {
        "count": len(recs),
        "recommendations": recs,
    }
