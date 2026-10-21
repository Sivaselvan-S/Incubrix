"""Hashnode GraphQL platform connector implementation."""

from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.connectors.base import BaseConnector


class HashnodeConnector(BaseConnector):
    """Hashnode developer blogging platform connector communicating via GraphQL."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def _get_url(self, destination: dict[str, Any]) -> str:
        settings = get_settings()
        if settings.SIMULATION_MODE:
            return f"{settings.MOCKHUB_URL}/graphql"
        return (
            destination.get("instance_config", {}).get("graphql_url")
            or destination.get("url")
            or settings.HASHNODE_URL
        )

    def _get_headers(self, connection: dict[str, Any]) -> dict[str, str]:
        settings = get_settings()
        token = connection.get("token") or settings.HASHNODE_TOKEN
        headers = {
            "Authorization": token,
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
        url = self._get_url(destination)
        headers = self._get_headers(connection)
        settings = get_settings()

        pub_id = (
            destination.get("instance_config", {}).get("publication_id")
            or destination.get("publication_id")
            or settings.HASHNODE_PUBLICATION_ID
        )

        query = """
        mutation PublishPost($input: PublishPostInput!) {
            publishPost(input: $input) {
                post {
                    id
                    url
                    title
                }
            }
        }
        """
        input_data = {
            "title": rendition.get("title", "Untitled Hashnode Post"),
            "contentMarkdown": rendition.get("body", ""),
            "publicationId": pub_id,
        }
        if rendition.get("canonical_url"):
            input_data["originalArticleURL"] = rendition["canonical_url"]

        payload = {"query": query, "variables": {"input": input_data}}

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Hashnode publish failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        if "errors" in data and not data.get("data"):
            raise ValueError(f"Hashnode GraphQL error: {data['errors']}")

        post = data.get("data", {}).get("publishPost", {}).get("post", {})
        post_id = str(post.get("id", ""))
        live_url = post.get("url") or f"https://blog.hashnode.dev/post-{post_id}"

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
        url = f"{settings.MOCKHUB_URL}/graphql" if settings.SIMULATION_MODE else settings.HASHNODE_URL
        headers = self._get_headers(connection)

        query = """
        query GetPost($id: String!) {
            post(id: $id) {
                id
                url
                title
            }
        }
        """
        payload = {"query": query, "variables": {"id": platform_post_id}}

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Hashnode get_status failed: {err['error']['code']} - {err['error']['message']}"
            )

        data = resp.json()
        post = data.get("data", {}).get("post")
        return {
            "platform_post_id": platform_post_id,
            "status": "published" if post else "not_found",
            "raw_response": data,
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        settings = get_settings()
        url = f"{settings.MOCKHUB_URL}/graphql" if settings.SIMULATION_MODE else settings.HASHNODE_URL
        headers = self._get_headers(connection)

        query = """
        mutation RemovePost($id: String!) {
            removePost(id: $id) {
                post {
                    id
                }
            }
        }
        """
        payload = {"query": query, "variables": {"id": platform_post_id}}

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code >= 400:
            err = self.map_http_status_to_error(resp.status_code, resp.text)
            raise ValueError(
                f"Hashnode delete failed: {err['error']['code']} - {err['error']['message']}"
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
            "type": "hashnode_assisted",
            "instructions": "Go to Hashnode Dashboard -> Write -> Paste Markdown body -> Publish.",
            "post_data": {
                "title": rendition.get("title", ""),
                "contentMarkdown": rendition.get("body", ""),
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
            post = status.get("raw_response", {}).get("data", {}).get("post", {})
            return {
                "views": post.get("views", 0),
                "reactions": post.get("reactions", 0),
            }
        except Exception:
            return {"views": 0, "reactions": 0}
