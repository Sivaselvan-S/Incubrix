"""Initializes and registers all platform connectors."""

from app.connectors.assisted.connector import AssistedConnector
from app.connectors.devto.connector import DevtoConnector
from app.connectors.discourse.connector import DiscourseConnector
from app.connectors.ghost.connector import GhostConnector
from app.connectors.hashnode.connector import HashnodeConnector
from app.connectors.lemmy.connector import LemmyConnector
from app.connectors.mrss_feed.connector import MRSSFeedConnector
from app.connectors.registry import register_connector
from app.connectors.slack.connector import SlackConnector
from app.connectors.webhook_hmac.connector import WebhookHmacConnector


def register_all_connectors() -> None:
    """Registers standard core and advanced connectors in the global registry."""
    register_connector("assisted", AssistedConnector())
    register_connector("webhook_hmac", WebhookHmacConnector())
    register_connector("discourse", DiscourseConnector())
    register_connector("devto", DevtoConnector())
    register_connector("lemmy", LemmyConnector())
    register_connector("ghost", GhostConnector())
    register_connector("mrss_feed", MRSSFeedConnector())
    register_connector("hashnode", HashnodeConnector())
    register_connector("slack", SlackConnector())
