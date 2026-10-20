"""Dynamic connector discovery and registry."""

from app.connectors.base import BaseConnector

# Global registry mapping connector_key -> Connector Class or instance
_REGISTRY: dict[str, BaseConnector] = {}


def register_connector(key: str, connector: BaseConnector) -> None:
    """Registers a connector instance under a given platform key."""
    _REGISTRY[key] = connector


def get_connector(key: str) -> BaseConnector:
    """Looks up and returns the registered connector for key without if/else branching.

    Raises KeyError if the connector key is not registered.
    """
    if key not in _REGISTRY:
        raise KeyError(f"Connector '{key}' is not registered in the system.")
    return _REGISTRY[key]


def list_connectors() -> list[str]:
    """Returns a list of all registered connector keys."""
    return list(_REGISTRY.keys())
