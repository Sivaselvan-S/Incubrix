"""Application configuration managed via Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration class populated from environment variables."""

    # Project metadata
    PROJECT_NAME: str = "LongTail Passport"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Simulation mode routes all connectors to Chaos Mock Hub
    SIMULATION_MODE: bool = True

    # Database: defaults to SQLite for fast standalone testing if Postgres not supplied
    DATABASE_URL: str = "sqlite:///./longtail_test.db"

    # MinIO / Object Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "passport-evidence"
    MINIO_SECURE: bool = False

    # Chaos Mock Hub URL
    MOCKHUB_URL: str = "http://localhost:8010"

    # Lemmy Settings
    LEMMY_URL: str = "http://localhost:8536"
    LEMMY_USERNAME: str = "incubrix_admin"
    LEMMY_PASSWORD: str = "lemmy_local_password_123"

    # Ghost Settings
    GHOST_URL: str = "http://localhost:2368"
    GHOST_ADMIN_API_KEY: str = (
        "64f8a7e0c4b6a1234567890a:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )

    # Hashnode Settings
    HASHNODE_URL: str = "https://gql.hashnode.com"
    HASHNODE_TOKEN: str = "mock_hashnode_token_123"
    HASHNODE_PUBLICATION_ID: str = "pub_mock_123"

    # Slack Settings
    SLACK_URL: str = "https://slack.com/api"
    SLACK_BOT_TOKEN: str = "xoxb-mock-token-1234567890"

    # AI Adapter
    LLM_PROVIDER: Literal["mock", "anthropic", "openai"] = "mock"
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # Worker & Janitor
    WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    RECERTIFICATION_INTERVAL_SECONDS: int = 86400
    DEMO_RECERTIFICATION_INTERVAL_SECONDS: int = 10
    JANITOR_RETENTION_MINUTES: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Returns cached application settings instance."""
    return Settings()
