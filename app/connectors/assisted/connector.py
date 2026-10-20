"""Assisted tier connector: prepares manual posting package with rule checklists."""

from pathlib import Path
from typing import Any

from app.connectors.base import BaseConnector


class AssistedConnector(BaseConnector):
    """Assisted connector producing download packs for destinations disallowing automation."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {"ok": True, "violations": []}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        pack = self.build_assist_pack(rendition, destination)
        return {
            "platform_post_id": f"assisted_{idempotency_key}",
            "live_url": destination.get("url", ""),
            "status": "assisted_pack_ready",
            "pack": pack,
        }

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {"status": "assisted_manual_action_required", "live_url": None}

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {"deleted": True}

    def build_assist_pack(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
    ) -> dict[str, Any]:
        checklist = [
            f"Navigate to {destination.get('url', 'the destination')}",
            "Paste the formatted caption into the submission form",
        ]
        if destination.get("disclosure_required"):
            checklist.append("Include AI transparency disclosure note")
        if not destination.get("self_promo_allowed"):
            checklist.append("Verify post contains zero direct promotional links")

        caption = f"{rendition.get('title', '')}\n\n{rendition.get('body', '')}".strip()
        return {
            "files": rendition.get("media", []),
            "caption": caption,
            "deep_link": destination.get("url", ""),
            "checklist": checklist,
            "destination_name": destination.get("name", ""),
        }
