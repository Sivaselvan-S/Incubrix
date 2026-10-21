"""Lemmy federated platform connector implementation."""

from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


class LemmyConnector(BaseConnector):
    """Lemmy platform connector communicating via Lemmy API v3."""

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
            or settings.LEMMY_URL
        )

    def _get_auth_token(self, connection: dict[str, Any], base_url: str) -> str:
        if connection.get("auth_token"):
            return connection["auth_token"]
        if connection.get("jwt"):
            return connection["jwt"]

        settings = get_settings()
        username = connection.get("username") or settings.LEMMY_USERNAME
        password = connection.get("password") or settings.LEMMY_PASSWORD

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{base_url}/api/v3/user/login",
                    json={"username_or_email": username, "password": password},
                )
                if resp.status_code == 200:
                    return resp.json().get("jwt", "mock_lemmy_jwt")
        except Exception:
            pass
        return "mock_lemmy_jwt"

    def _get_headers(self, connection: dict[str, Any], token: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
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
        token = self._get_auth_token(connection, base_url)
        headers = self._get_headers(connection, token)

        payload = {
            "name": rendition.get("title", "Untitled Lemmy Post"),
            "body": rendition.get("body", ""),
            "community_id": destination.get("community_id", 1),
            "auth": token,
        }

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{base_url}/api/v3/post", json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Lemmy publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post_obj = data.get("post_view", {}).get("post", {})
        post_id = str(post_obj.get("id", ""))
        live_url = post_obj.get("ap_id") or f"{base_url}/post/{post_id}"

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
            else connection.get("base_url", settings.LEMMY_URL)
        )
        token = self._get_auth_token(connection, base_url)
        headers = self._get_headers(connection, token)

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                f"{base_url}/api/v3/post", params={"id": platform_post_id}, headers=headers
            )

        if resp.status_code == 404:
            return {"platform_post_id": platform_post_id, "status": "deleted", "live_url": None}

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Lemmy get_status failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post = data.get("post_view", {}).get("post", {})
        status = "deleted" if post.get("deleted") else "published"
        return {
            "platform_post_id": platform_post_id,
            "status": status,
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
            else connection.get("base_url", settings.LEMMY_URL)
        )
        token = self._get_auth_token(connection, base_url)
        headers = self._get_headers(connection, token)

        try:
            pid = int(platform_post_id)
        except ValueError:
            pid = platform_post_id

        payload = {
            "post_id": pid,
            "deleted": True,
            "auth": token,
        }

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{base_url}/api/v3/post/delete", json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Lemmy delete failed: {err['error']['code']} - {err['error']['message']}"
            )

        return {
            "platform_post_id": platform_post_id,
            "status": "deleted",
            "raw_response": resp.json(),
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
            "type": "lemmy_assisted",
            "instructions": "Open Lemmy instance community and paste post title and body.",
            "post_data": {
                "name": rendition.get("title", ""),
                "body": rendition.get("body", ""),
                "community_id": destination.get("community_id", 1),
            },
        }

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            status = self.get_status(platform_post_id, connection)
            counts = status.get("raw_response", {}).get("post_view", {}).get("counts", {})
            return {
                "score": counts.get("score", 0),
                "upvotes": counts.get("upvotes", 0),
                "downvotes": counts.get("downvotes", 0),
                "comments": counts.get("comments", 0),
            }
        except Exception:
            return {"score": 0, "comments": 0}
