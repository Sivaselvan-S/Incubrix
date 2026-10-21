"""Slack platform connector implementation communicating via Slack Web API."""

from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


class SlackConnector(BaseConnector):
    """Slack messaging platform connector communicating via Slack Web API."""

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
            or settings.SLACK_URL
        )

    def _get_headers(self, connection: dict[str, Any]) -> dict[str, str]:
        settings = get_settings()
        token = connection.get("bot_token") or settings.SLACK_BOT_TOKEN
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
        body = rendition.get("body", "")
        if len(body) > 40000:
            violations.append(
                {"field": "body", "rule": "max_chars", "limit": 40000, "actual": len(body)}
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
        url = f"{base_url}/api/chat.postMessage"
        headers = self._get_headers(connection)

        channel = (
            destination.get("instance_config", {}).get("channel")
            or destination.get("channel")
            or "general"
        )
        title = rendition.get("title", "")
        body = rendition.get("body", "")
        text = f"*{title}*\n\n{body}" if title else body

        payload = {
            "channel": channel,
            "text": text,
        }

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Slack publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        if not data.get("ok"):
            err_msg = data.get("error", "unknown_error")
            raise ValueError(f"Slack postMessage failed: {err_msg}")

        ts = data.get("ts", "")
        clean_ts = ts.replace(".", "")
        live_url = f"https://slack.com/archives/{channel}/p{clean_ts}"

        return {
            "platform_post_id": ts,
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
            else connection.get("base_url", settings.SLACK_URL)
        )
        channel = connection.get("channel", "general")
        url = f"{base_url}/api/conversations.history"
        headers = self._get_headers(connection)

        with httpx.Client(timeout=5.0) as client:
            resp = client.get(
                url, params={"channel": channel, "ts": platform_post_id}, headers=headers
            )

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Slack get_status failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        ok = data.get("ok", False)
        return {
            "platform_post_id": platform_post_id,
            "status": "published" if ok else "not_found",
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
            else connection.get("base_url", settings.SLACK_URL)
        )
        channel = connection.get("channel", "general")
        url = f"{base_url}/api/chat.delete"
        headers = self._get_headers(connection)

        payload = {"channel": channel, "ts": platform_post_id}

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Slack delete failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        if not data.get("ok"):
            err_msg = data.get("error", "unknown_error")
            raise ValueError(f"Slack chat.delete failed: {err_msg}")

        return {
            "platform_post_id": platform_post_id,
            "status": "deleted",
            "raw_response": data,
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
            "type": "slack_assisted",
            "instructions": f"Open Slack -> Channel #{destination.get('channel', 'general')} -> Paste message.",
            "post_data": {
                "channel": destination.get("channel", "general"),
                "text": rendition.get("body", ""),
            },
        }

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            status = self.get_status(platform_post_id, connection)
            messages = status.get("raw_response", {}).get("messages", [{}])
            msg = messages[0] if messages else {}
            reactions = len(msg.get("reactions", []))
            reply_count = msg.get("reply_count", 0)
            return {
                "reactions": reactions,
                "replies": reply_count,
            }
        except Exception:
            return {"reactions": 0, "replies": 0}
