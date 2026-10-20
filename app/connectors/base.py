"""Abstract Base Connector specification and standard error mapper."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

SHARED_ERROR_CODES = {
    "DEST_SPEC_VIOLATION": {"retryable": False, "action": "return field-level reasons"},
    "DEST_RULE_FREQUENCY_CAP": {"retryable": "later", "action": "reschedule after cap window"},
    "CONNECTION_AUTH_EXPIRED": {
        "retryable": "after reconnect",
        "action": "pause, ask owner to reconnect",
    },
    "PLATFORM_RATE_LIMIT": {"retryable": True, "action": "back off using reset time"},
    "PLATFORM_QUOTA_EXHAUSTED": {"retryable": "next window", "action": "reschedule"},
    "PLATFORM_CONTENT_REJECTED": {
        "retryable": False,
        "action": "return platform message for review",
    },
    "PLATFORM_UNAVAILABLE": {
        "retryable": True,
        "action": "retry; circuit-break after 5 consecutive failures",
    },
    "CONNECTOR_DISABLED": {"retryable": False, "action": "kill switch on"},
    "IDEMPOTENCY_KEY_REUSED": {"retryable": False, "action": "use unique key or same payload"},
    "CERT_DRIFT_DETECTED": {"retryable": False, "action": "demote destination and update schema"},
    "DEST_RULE_PROMO_BLOCKED": {"retryable": False, "action": "reframe as non-promotional"},
    "DEST_RULE_LINK_POLICY": {"retryable": False, "action": "adjust links according to policy"},
    "DEST_RULE_AI_DISCLOSURE_REQUIRED": {
        "retryable": False,
        "action": "include transparency notice",
    },
    "DESTINATION_DEMOTED": {"retryable": False, "action": "recertify destination"},
    "JOB_NOT_FOUND": {"retryable": False, "action": "verify job id"},
    "VALIDATION_ERROR": {"retryable": False, "action": "fix request schema"},
}


class ConnectorManifest(BaseModel):
    """Parsed manifest.yaml for a connector."""

    key: str
    version: str
    tier: str  # native | bridge | assisted
    auth: dict[str, Any] = {}
    surfaces: dict[str, Any] = {}
    rate_limits: dict[str, Any] = {}
    capabilities: dict[str, Any] = {}
    error_map: dict[str, str] = {}
    instance_param: str | None = None
    response_schema_ref: dict[str, str] = {}


class BaseConnector(ABC):
    """Abstract Connector contract implemented by all long-tail platforms."""

    manifest: ConnectorManifest

    def __init__(self, manifest_path: Path | str | None = None) -> None:
        if manifest_path:
            self.manifest = self.load_manifest(Path(manifest_path))

    @staticmethod
    def load_manifest(path: Path) -> ConnectorManifest:
        """Loads and validates a connector's manifest.yaml file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return ConnectorManifest(**data)

    def map_http_status_to_error(
        self,
        status_code: int,
        response_body: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Maps an HTTP status code to shared error codes using manifest error_map and standard conventions."""
        str_status = str(status_code)
        manifest_map = self.manifest.error_map if hasattr(self, "manifest") else {}

        # 1. Check custom override in connector manifest
        error_code = manifest_map.get(str_status)

        # 2. Default standard status code fallbacks
        if not error_code:
            if status_code == 400:
                error_code = "DEST_SPEC_VIOLATION"
            elif status_code == 401 or status_code == 403:
                error_code = "CONNECTION_AUTH_EXPIRED"
            elif status_code == 422:
                error_code = "PLATFORM_CONTENT_REJECTED"
            elif status_code == 429:
                error_code = "PLATFORM_RATE_LIMIT"
            elif status_code >= 500:
                error_code = "PLATFORM_UNAVAILABLE"
            else:
                error_code = "PLATFORM_CONTENT_REJECTED"

        meta = SHARED_ERROR_CODES.get(error_code, {"retryable": False, "action": "review response"})
        is_retryable = bool(meta.get("retryable", False))

        msg = f"Platform responded with HTTP {status_code}"
        if isinstance(response_body, dict) and "message" in response_body:
            msg = str(response_body["message"])
        elif isinstance(response_body, str) and response_body:
            msg = response_body[:200]

        return {
            "error": {
                "code": error_code,
                "message": msg,
                "retryable": is_retryable,
                "details": {
                    "http_status": status_code,
                    "action": meta.get("action", ""),
                    "raw_response": response_body,
                },
            }
        }

    # --------------------------------------------------------------------------
    # Mandatory Connector Contract Methods
    # --------------------------------------------------------------------------

    @abstractmethod
    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        """Validates rendition against destination limits.

        Returns: {"ok": bool, "violations": list[{"field", "rule", "limit", "actual"}]}
        """
        pass

    @abstractmethod
    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Publishes content to the platform.

        Returns: {"platform_post_id": str, "live_url": str, "status": str}
        """
        pass

    @abstractmethod
    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        """Queries the current status of an external publication.

        Returns: {"status": str, "live_url": str | None}
        """
        pass

    @abstractmethod
    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        """Deletes or unpublishes a previously published post.

        Returns: {"deleted": bool}
        """
        pass

    # --------------------------------------------------------------------------
    # Optional Extension Contract Methods
    # --------------------------------------------------------------------------

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """Fetches engagement metrics for a post.

        Returns: {"views": int, "likes": int, "comments": int, "shares": int, "clicks": int}
        """
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0}

    def refresh_auth(self, connection: dict[str, Any]) -> dict[str, Any]:
        """Refreshes expiring auth tokens if supported by platform."""
        return {"expires_at": None}

    def build_assist_pack(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
    ) -> dict[str, Any]:
        """Builds an assisted tier publishing package (caption, files, deep_link, checklist)."""
        return {
            "files": [],
            "caption": rendition.get("title", "") + "\n\n" + rendition.get("body", ""),
            "deep_link": destination.get("url", ""),
            "checklist": ["Review destination rules", "Verify formatting"],
        }
