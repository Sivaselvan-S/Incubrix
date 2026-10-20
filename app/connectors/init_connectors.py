"""Initializes and registers all platform connectors."""

from app.connectors.assisted.connector import AssistedConnector
from app.connectors.devto.connector import DevtoConnector
from app.connectors.discourse.connector import DiscourseConnector
from app.connectors.registry import register_connector
from app.connectors.webhook_hmac.connector import WebhookHmacConnector


def register_all_connectors() -> None:
    """Registers standard core connectors in the global registry."""
    register_connector("assisted", AssistedConnector())
    register_connector("webhook_hmac", WebhookHmacConnector())
    register_connector("discourse", DiscourseConnector())
    register_connector("devto", DevtoConnector())
