"""Ghost publishing connector implementation using Ghost Admin API."""

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


def generate_ghost_admin_jwt(api_key: str) -> str:
    """Generates an HS256 JWT for Ghost Admin API authentication without external dependencies."""
    try:
        key_id, secret = api_key.split(":")
        secret_bytes = bytes.fromhex(secret)
    except Exception:
        # Fallback for mock tokens
        return f"mock_ghost_jwt_{api_key}"

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {"iat": now, "exp": now + 300, "aud": "/admin/"}

    h_b64 = (
        base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )
    p_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .rstrip(b"=")
        .decode()
    )
    signing_input = f"{h_b64}.{p_b64}".encode()
    signature = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    return f"{h_b64}.{p_b64}.{sig_b64}"


class GhostConnector(BaseConnector):
    """Ghost platform connector communicating with Ghost Admin API v5."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def _get_base_url(self, destination: dict[str, Any]) -> str:
        settings = get_settings()
        if settings.SIMULATION_MODE:
            return settings.MOCKHUB_URL
        return (
            destination.get("instance_config", {}).get("base_url")
            or destination.get("url")
            or settings.GHOST_URL
        )

    def _get_headers(self, connection: dict[str, Any]) -> dict[str, str]:
        settings = get_settings()
        api_key = connection.get("admin_api_key") or settings.GHOST_ADMIN_API_KEY
        token = generate_ghost_admin_jwt(api_key)
        headers = {
            "Authorization": f"Ghost {token}",
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
        url = f"{base_url}/ghost/api/admin/posts/?source=html"
        headers = self._get_headers(connection)

        post_data = {
            "title": rendition.get("title", "Untitled Post"),
            "html": rendition.get("body", ""),
            "status": "published",
        }
        if rendition.get("canonical_url"):
            post_data["canonical_url"] = rendition["canonical_url"]

        payload = {"posts": [post_data]}

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Ghost publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post_obj = data.get("posts", [{}])[0]
        post_id = str(post_obj.get("id", ""))
        live_url = post_obj.get("url") or f"{base_url}/{post_id}/"

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
        base_url = (
            settings.MOCKHUB_URL
            if settings.SIMULATION_MODE
            else connection.get("base_url", settings.GHOST_URL)
        )
        url = f"{base_url}/ghost/api/admin/posts/{platform_post_id}/"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=headers)

        if resp.status_code == 404:
            return {"platform_post_id": platform_post_id, "status": "deleted", "live_url": None}

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Ghost get_status failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post_obj = data.get("posts", [{}])[0]
        return {
            "platform_post_id": platform_post_id,
            "status": post_obj.get("status", "published"),
            "raw_response": data,
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        settings = get_settings()
        base_url = (
            settings.MOCKHUB_URL
            if settings.SIMULATION_MODE
            else connection.get("base_url", settings.GHOST_URL)
        )
        url = f"{base_url}/ghost/api/admin/posts/{platform_post_id}/"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.delete(url, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Ghost delete failed: {err['error']['code']} - {err['error']['message']}"
            )

        return {
            "platform_post_id": platform_post_id,
            "status": "deleted",
            "raw_response": {"deleted": True, "id": platform_post_id},
        }

    def live_check(
        self,
        platform_post_id: str,
        destination: dict[str, Any],
    ) -> bool:
        try:
            status = self.get_status(platform_post_id, destination.get("connection", {}))
            return status.get("status") == "published"
        except Exception:
            return False

    def build_assist_pack(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "ghost_assisted",
            "instructions": "Log in to Ghost Admin dashboard -> Posts -> New post -> paste HTML.",
            "post_data": {
                "title": rendition.get("title", ""),
                "html": rendition.get("body", ""),
                "canonical_url": rendition.get("canonical_url"),
            },
        }

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            status = self.get_status(platform_post_id, connection)
            post = status.get("raw_response", {}).get("posts", [{}])[0]
            count = post.get("count", {})
            return {
                "views": count.get("views", 0),
                "clicks": count.get("clicks", 0),
                "comments": count.get("comments", 0),
            }
        except Exception:
            return {"views": 0, "comments": 0}
