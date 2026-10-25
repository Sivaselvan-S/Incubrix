"""Storage adapter supporting S3/MinIO in production and robust local persistence in tests."""

import json
from pathlib import Path
from typing import Any
import httpx

from app.config import get_settings
from app.logging import get_logger

logger = get_logger("app.storage")


class StorageClient:
    """Manages evidence and artifact storage for certification packs and assist downloads."""

    def __init__(self):
        self.settings = get_settings()
        self.base_dir = Path("storage") / "evidence"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_evidence(
        self,
        relative_path: str,
        data: bytes | str | dict[str, Any],
        content_type: str = "application/json",
    ) -> str:
        """Saves evidence and returns the canonical evidence URI.

        In simulation/test mode: writes to local storage directory.
        In production with MinIO: uploads to S3 bucket.
        """
        if isinstance(data, dict):
            raw_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        elif isinstance(data, str):
            raw_bytes = data.encode("utf-8")
        else:
            raw_bytes = data

        clean_path = relative_path.lstrip("/")

        # Local storage mirror
        file_path = self.base_dir / clean_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(raw_bytes)

        if not self.settings.SIMULATION_MODE and self.settings.MINIO_ENDPOINT:
            # Upload to MinIO HTTP endpoint
            protocol = "https" if self.settings.MINIO_SECURE else "http"
            url = f"{protocol}://{self.settings.MINIO_ENDPOINT}/{self.settings.MINIO_BUCKET}/{clean_path}"
            try:
                with httpx.Client(timeout=5.0) as client:
                    client.put(
                        url,
                        content=raw_bytes,
                        headers={"Content-Type": content_type},
                        auth=(self.settings.MINIO_ACCESS_KEY, self.settings.MINIO_SECRET_KEY),
                    )
                return f"s3://{self.settings.MINIO_BUCKET}/{clean_path}"
            except Exception as exc:
                logger.warning("MinIO upload failed, fell back to local storage: %s", exc)

        return f"s3://{self.settings.MINIO_BUCKET}/{clean_path}"

    def get_evidence(self, relative_path: str) -> bytes | None:
        """Retrieves raw evidence bytes from storage."""
        clean_path = relative_path.lstrip("/")
        file_path = self.base_dir / clean_path
        if file_path.exists():
            return file_path.read_bytes()
        return None


_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """Returns singleton StorageClient instance."""
    global _storage_client
    if _storage_client is None:
        _storage_client = StorageClient()
    return _storage_client
