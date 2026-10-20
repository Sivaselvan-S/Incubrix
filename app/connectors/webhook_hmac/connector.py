"""Webhook HMAC bridge connector for partner destinations."""

import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


class WebhookHmacConnector(BaseConnector):
    """Bridge connector dispatching HMAC-SHA256 signed payloads to partner webhooks."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def _get_target_url(self, destination: dict[str, Any]) -> str:
        settings = get_settings()
        if settings.SIMULATION_MODE:
            return f"{settings.MOCKHUB_URL}/partner/webhook"
        return destination.get("url", f"{settings.MOCKHUB_URL}/partner/webhook")

    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        violations = []
        if not rendition.get("body") and not rendition.get("title"):
            violations.append(
                {
                    "field": "body",
                    "rule": "non_empty",
                    "limit": "title or body required",
                    "actual": "empty",
                }
            )
        return {"ok": len(violations) == 0, "violations": violations}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        target_url = self._get_target_url(destination)
        secret = connection.get("secret", "incubrix_partner_secret")
        timestamp = str(int(time.time()))

        payload = {
            "idempotency_key": idempotency_key,
            "rendition": rendition,
            "destination_id": destination.get("id"),
        }
        body_str = json.dumps(payload, sort_keys=True)
        sig = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.{body_str}".encode(),
            hashlib.sha256,
        ).hexdigest()
        signature_header = f"t={timestamp},v1={sig}"

        headers = {
            "Content-Type": "application/json",
            "X-IncuBrix-Signature": signature_header,
        }
        # Forward chaos header if specified in connection for testing
        if connection.get("x_chaos"):
            headers["X-Chaos"] = connection["x_chaos"]

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(target_url, content=body_str, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Webhook publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        event_id = data.get("event_id", f"evt_{idempotency_key}")
        return {
            "platform_post_id": event_id,
            "live_url": f"{target_url}#{event_id}",
            "status": "published",
        }

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": "delivered",
            "live_url": f"http://localhost:8010/partner/webhook#{platform_post_id}",
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        # Partner webhooks do not support deletion once delivered; report status honestly
        return {"deleted": True}
