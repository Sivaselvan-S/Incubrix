"""Streaming CSV catalogue importer with URL normalization, deduplication, and batch upsert."""

import csv
import io
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.catalogue.reachability import check_url_reachability
from app.db.models import DestinationModel, PassportModel
from app.logging import get_logger

logger = get_logger("app.catalogue.importer")

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "fbclid",
    "gclid",
}


def normalize_destination_url(url: str) -> str:
    """Normalizes destination URL by stripping www, trailing slashes, and marketing tracking params."""
    if not url:
        return ""
    clean = url.strip()
    if not clean.lower().startswith(("http://", "https://")):
        clean = f"https://{clean}"

    parsed = urllib.parse.urlsplit(clean)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path.rstrip("/")
    if not path:
        path = ""

    # Filter out tracking query parameters
    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_params = [
        (k, v) for k, v in query_params if k.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urllib.parse.urlencode(filtered_params)

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def import_catalogue_csv(
    db: Session,
    csv_source: str | Path | Iterable[str],
    batch_size: int = 500,
    verify_reachability: bool = False,
) -> dict[str, Any]:
    """Streams and ingests destinations from CSV data with deduplication and batch insertion.

    Expected CSV columns:
    name, url, platform_key, surface, category, language, frequency_cap_days, self_promo_allowed, disclosure_required
    """
    if isinstance(csv_source, Path):
        file_obj = csv_source.open("r", encoding="utf-8")
        reader = csv.DictReader(file_obj)
    elif isinstance(csv_source, str) and "\n" in csv_source:
        file_obj = io.StringIO(csv_source)
        reader = csv.DictReader(file_obj)
    elif isinstance(csv_source, str) and Path(csv_source).exists():
        file_obj = Path(csv_source).open("r", encoding="utf-8")
        reader = csv.DictReader(file_obj)
    else:
        reader = csv.DictReader(csv_source)

    total_read = 0
    imported = 0
    duplicates_skipped = 0
    unreachable_count = 0
    batch: list[DestinationModel] = []
    seen_urls_in_batch: set[str] = set()

    # Pre-fetch existing normalized URLs to avoid database round-trips
    existing_urls = {
        row[0] for row in db.query(DestinationModel.url).all() if row[0]
    }

    try:
        for row in reader:
            total_read += 1
            raw_url = row.get("url", "")
            if not raw_url:
                continue

            normalized_url = normalize_destination_url(raw_url)
            if normalized_url in existing_urls or normalized_url in seen_urls_in_batch:
                duplicates_skipped += 1
                continue

            # Optional Reachability Check
            if verify_reachability:
                import asyncio
                reachable, _, _ = asyncio.run(check_url_reachability(normalized_url))
                if not reachable:
                    unreachable_count += 1
                    continue

            platform_key = (row.get("platform_key") or "discourse").strip()
            surface = (row.get("surface") or "community").strip()
            category = (row.get("category") or "general").strip()
            language = (row.get("language") or "en").strip()
            connector_key = (row.get("connector_key") or platform_key).strip()

            # Parse frequency cap: support "1/7d" format, numeric days, or frequency_cap_days
            freq_raw = row.get("frequency_cap") or row.get("frequency_cap_days") or "7"
            if isinstance(freq_raw, str) and "/" in freq_raw:
                try:
                    parts = freq_raw.split("/")
                    max_posts = int(parts[0])
                    days_str = parts[1].rstrip("dD")
                    freq_days = int(days_str)
                    freq_cap = {"max": max_posts, "per_days": freq_days}
                except Exception:
                    freq_cap = {"max": 1, "per_days": 7}
            else:
                try:
                    freq_days = int(freq_raw)
                except Exception:
                    freq_days = 7
                freq_cap = {"max": 1, "per_days": freq_days}

            self_promo = str(row.get("self_promo_allowed", "true")).lower() in ("true", "1", "yes")
            disclosure = str(row.get("disclosure_required", "false")).lower() in ("true", "1", "yes")
            automation = str(row.get("automation_allowed", "true")).lower() in ("true", "1", "yes")

            # Parse audience tags
            raw_tags = row.get("audience_tags", "")
            if isinstance(raw_tags, list):
                audience_tags = raw_tags
            elif isinstance(raw_tags, str) and raw_tags.strip():
                if ";" in raw_tags:
                    audience_tags = [t.strip() for t in raw_tags.split(";") if t.strip()]
                elif "," in raw_tags:
                    audience_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                else:
                    audience_tags = [raw_tags.strip()]
            else:
                audience_tags = []

            # Parse estimated audience
            raw_aud = row.get("est_audience")
            try:
                est_aud = int(raw_aud) if raw_aud is not None and str(raw_aud).strip().isdigit() else None
            except Exception:
                est_aud = None

            # Parse relevance score
            raw_rel = row.get("relevance_score") or row.get("relevance_score (1-5)") or 3.0
            try:
                rel_score = float(raw_rel)
            except Exception:
                rel_score = 3.0

            dest = DestinationModel(
                name=row.get("name", "Unnamed Destination").strip(),
                url=normalized_url,
                platform_key=platform_key,
                connector_key=connector_key,
                surface=surface,
                category=category,
                audience_tags=audience_tags,
                language=language,
                geo=row.get("geo"),
                est_audience=est_aud,
                rules_url=row.get("rules_url"),
                frequency_cap_json=freq_cap,
                self_promo_allowed=self_promo,
                link_policy=row.get("link_policy", "none"),
                disclosure_required=disclosure,
                automation_allowed=automation,
                relevance_score=rel_score,
                relevance_reason=row.get("relevance_reason"),
                status="active",
                level=row.get("level", "L0"),
            )
            batch.append(dest)
            seen_urls_in_batch.add(normalized_url)

            if len(batch) >= batch_size:
                db.add_all(batch)
                db.flush()
                # Create initial L0 passports
                for d in batch:
                    passport = PassportModel(destination_id=d.id, level="L0", health_score=50.0)
                    db.add(passport)
                db.commit()
                imported += len(batch)
                existing_urls.update(seen_urls_in_batch)
                batch.clear()
                seen_urls_in_batch.clear()

        # Commit remaining rows in final batch
        if batch:
            db.add_all(batch)
            db.flush()
            for d in batch:
                passport = PassportModel(destination_id=d.id, level="L0", health_score=50.0)
                db.add(passport)
            db.commit()
            imported += len(batch)

    finally:
        if "file_obj" in locals() and hasattr(file_obj, "close"):
            file_obj.close()

    logger.info(
        "Catalogue import completed: read=%d, imported=%d, dupes=%d, unreachable=%d",
        total_read,
        imported,
        duplicates_skipped,
        unreachable_count,
    )

    return {
        "total_read": total_read,
        "imported": imported,
        "duplicates_skipped": duplicates_skipped,
        "unreachable": unreachable_count,
    }
