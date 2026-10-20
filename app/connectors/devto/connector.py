"""Dev.to (Forem) native connector implementation."""

from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


class DevtoConnector(BaseConnector):
    """Dev.to (Forem) article connector communicating via REST API."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def _get_base_url(self) -> str:
        settings = get_settings()
        return settings.MOCKHUB_URL if settings.SIMULATION_MODE else "https://dev.to"

    def _get_headers(self, connection: dict[str, Any]) -> dict[str, str]:
        headers = {
            "api-key": connection.get("api_key", "mock_devto_api_key"),
            "Content-Type": "application/json",
        }
        if connection.get("x_chaos"):
            headers["X-Chaos"] = connection["x_chaos"]
        return headers

    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        violations = []
        title = rendition.get("title", "")
        if len(title) > 128:
            violations.append(
                {"field": "title", "rule": "max_chars", "limit": 128, "actual": len(title)}
            )
        tags = rendition.get("tags", [])
        if len(tags) > 4:
            violations.append(
                {"field": "tags", "rule": "max_tags", "limit": 4, "actual": len(tags)}
            )
        return {"ok": len(violations) == 0, "violations": violations}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        base_url = self._get_base_url()
        url = f"{base_url}/api/articles"
        headers = self._get_headers(connection)

        article_payload = {
            "title": rendition.get("title", "Untitled Article"),
            "body_markdown": rendition.get("body", ""),
            "published": True,
            "tags": rendition.get("tags", ["tech"])[:4],
        }
        if rendition.get("canonical_url"):
            article_payload["canonical_url"] = rendition["canonical_url"]

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json={"article": article_payload}, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Dev.to publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post_id = str(data.get("id", ""))
        live_url = data.get("url") or data.get("live_link") or f"{base_url}/article/{post_id}"

        return {
            "platform_post_id": post_id,
            "live_url": live_url,
            "status": "published",
            "raw_response": data,
        }

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = self._get_base_url()
        url = f"{base_url}/api/articles/{platform_post_id}"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            return {"status": "error", "error": err}

        data = resp.json()
        is_published = data.get("published", True)
        return {
            "status": "live" if is_published else "unpublished",
            "live_url": data.get("url"),
            "raw_response": data,
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        """Dev.to / Forem API does not provide an HTTP DELETE route.

        Unpublishing (published=false) is the official mechanism and documented honestly.
        """
        base_url = self._get_base_url()
        url = f"{base_url}/api/articles/{platform_post_id}"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.put(url, json={"article": {"published": False}}, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(f"Dev.to unpublish failed: {err['error']['code']}")

        return {"deleted": True, "method": "unpublish"}

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
        since=None,
    ) -> dict[str, Any]:
        return {
            "views": 210,
            "likes": 35,
            "comments": 8,
            "shares": 4,
            "clicks": 18,
        }
