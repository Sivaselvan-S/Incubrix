"""Catalogue import API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.catalogue.importer import import_catalogue_csv

router = APIRouter(prefix="/api/v1/destinations", tags=["catalogue"])


class ImportTextRequest(BaseModel):
    """Payload containing raw CSV text content."""

    csv_content: str


@router.post("/import-csv", status_code=status.HTTP_201_CREATED)
async def import_csv_file(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingests and streams destinations from an uploaded CSV file or raw CSV text."""
    content_type = request.headers.get("content-type", "")
    csv_text: str | None = None

    if "application/json" in content_type:
        body = await request.json()
        csv_text = body.get("csv_content")
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            content = await uploaded_file.read()
            csv_text = content.decode("utf-8", errors="replace")
        else:
            csv_text = form.get("csv_content")

    if not csv_text or not str(csv_text).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either a file upload or csv_content in payload.",
        )

    summary = import_catalogue_csv(db, csv_text)
    return {
        "status": "completed",
        "summary": summary,
    }
