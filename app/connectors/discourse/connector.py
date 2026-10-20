"""Discourse native connector implementation."""

from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


class DiscourseConnector(BaseConnector):
    """Discourse platform connector communicating via REST API."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def _get_base_url(self, destination: dict[str, Any]) -> str:
        settings = get_settings()
        if settings.SIMULATION_MODE:
            return settings.MOCKHUB_URL
        return destination.get("instance_config", {}).get("base_url") or destination.get(
            "url", settings.MOCKHUB_URL
        )

    def _get_headers(self, connection: dict[str, Any]) -> dict[str, str]:
        headers = {
            "Api-Key": connection.get("api_key", "mock_discourse_api_key"),
            "Api-Username": connection.get("api_username", "system"),
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
        if len(title) > 255:
            violations.append(
                {"field": "title", "rule": "max_chars", "limit": 255, "actual": len(title)}
            )
        return {"ok": len(violations) == 0, "violations": violations}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        base_url = self._get_base_url(destination)
        url = f"{base_url}/posts.json"
        headers = self._get_headers(connection)

        payload = {
            "title": rendition.get("title", "Untitled Post"),
            "raw": rendition.get("body", ""),
            "category": destination.get("category"),
        }

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Discourse publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post_id = str(data.get("id") or data.get("post_identifier", ""))
        live_url = data.get("live_url") or f"{base_url}/t/{data.get('topic_id', 1)}/{post_id}"

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
        settings = get_settings()
        base_url = settings.MOCKHUB_URL
        url = f"{base_url}/posts/{platform_post_id}.json"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=headers)

        if resp.status_code == 404:
            return {"status": "deleted", "live_url": None}

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            return {"status": "error", "error": err}

        data = resp.json()
        return {
            "status": "live" if not data.get("deleted") else "deleted",
            "live_url": f"{base_url}/t/{data.get('topic_id', 1)}/{platform_post_id}",
            "raw_response": data,
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        settings = get_settings()
        base_url = settings.MOCKHUB_URL
        url = f"{base_url}/posts/{platform_post_id}.json"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.delete(url, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(f"Discourse delete failed: {err['error']['code']}")

        return {"deleted": True}

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
        since=None,
    ) -> dict[str, Any]:
        return {
            "views": 45,
            "likes": 12,
            "comments": 3,
            "shares": 0,
            "clicks": 8,
        }
